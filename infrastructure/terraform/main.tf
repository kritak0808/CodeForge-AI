provider "aws" {
  region = var.aws_region
}

# 1. VPC network architecture definitions
resource "aws_vpc" "codeforge_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "codeforge-${var.environment}-vpc"
    Environment = var.environment
  }
}

# subnets for high availability
resource "aws_subnet" "subnet_a" {
  vpc_id            = aws_vpc.codeforge_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = {
    Name = "codeforge-${var.environment}-subnet-a"
  }
}

resource "aws_subnet" "subnet_b" {
  vpc_id            = aws_vpc.codeforge_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"
  tags = {
    Name = "codeforge-${var.environment}-subnet-b"
  }
}

# 2. Ephemeral container execution subnet definitions (Firewalled VPC)
resource "aws_subnet" "sandbox_subnet" {
  vpc_id            = aws_vpc.codeforge_vpc.id
  cidr_block        = "10.0.99.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name        = "codeforge-${var.environment}-sandbox-subnet"
    Environment = var.environment
  }
}

# Security Groups
resource "aws_security_group" "cf_sg" {
  name        = "codeforge-${var.environment}-sg"
  description = "CodeForge common security group"
  vpc_id      = aws_vpc.codeforge_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. AWS RDS PostgreSQL Database
resource "aws_db_subnet_group" "db_subnet" {
  name       = "codeforge-db-subnet-group"
  subnet_ids = [aws_subnet.subnet_a.id, aws_subnet.subnet_b.id]
}

resource "aws_db_instance" "postgres_db" {
  identifier             = "codeforge-${var.environment}-db"
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = "db.t4g.medium"
  db_name                = "codeforge_production"
  username               = "postgres"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.db_subnet.name
  vpc_security_group_ids = [aws_security_group.cf_sg.id]
  skip_final_snapshot    = true
}

# 4. ElastiCache Redis Replication Group
resource "aws_elasticache_subnet_group" "redis_subnet" {
  name       = "codeforge-redis-subnet-group"
  subnet_ids = [aws_subnet.subnet_a.id, aws_subnet.subnet_b.id]
}

resource "aws_elasticache_replication_group" "redis_rg" {
  replication_group_id        = "codeforge-${var.environment}-redis"
  description                 = "Redis cache replication group"
  node_type                   = "cache.t4g.medium"
  num_cache_clusters          = 2
  parameter_group_name        = "default.redis7"
  port                        = 6379
  subnet_group_name           = aws_elasticache_subnet_group.redis_subnet.name
  security_group_ids          = [aws_security_group.cf_sg.id]
  auth_token                  = var.redis_password
  transit_encryption_enabled = true
}

# 5. Amazon MSK Kafka Cluster
resource "aws_msk_cluster" "kafka_cluster" {
  cluster_name           = "codeforge-${var.environment}-kafka"
  kafka_version          = "3.2.0"
  number_of_broker_nodes = 2

  broker_node_group_info {
    instance_type = "kafka.t3.small"
    client_subnets = [
      aws_subnet.subnet_a.id,
      aws_subnet.subnet_b.id
    ]
    security_groups = [aws_security_group.cf_sg.id]
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  tags = {
    Environment = var.environment
  }
}

# 6. AWS EKS Kubernetes Cluster
resource "aws_iam_role" "eks_cluster_role" {
  name = "codeforge-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "eks_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster_role.name
}

resource "aws_eks_cluster" "eks_cluster" {
  name     = "codeforge-${var.environment}-eks"
  role_arn = aws_iam_role.eks_cluster_role.arn

  vpc_config {
    subnet_ids = [aws_subnet.subnet_a.id, aws_subnet.subnet_b.id]
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_policy
  ]
}
