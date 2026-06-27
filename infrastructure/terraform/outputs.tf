output "vpc_id" {
  value = aws_vpc.codeforge_vpc.id
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.eks_cluster.endpoint
}

output "db_endpoint" {
  value = aws_db_instance.postgres_db.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis_rg.primary_endpoint_address
}

output "kafka_brokers" {
  value = aws_msk_cluster.kafka_cluster.bootstrap_brokers_tls
}
