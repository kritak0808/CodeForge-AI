'use client';

import { useRouter, usePathname } from 'next/navigation';
import {
  LayoutDashboard, GitBranch, Zap, Clock, Cpu,
  Database, BarChart3, DollarSign, Shield, Settings, LogOut,
} from 'lucide-react';
import { logout, getCurrentUser } from '../lib/auth';

const NAV = [
  { href: '/',            icon: LayoutDashboard, label: 'Dashboard'    },
  { href: '/projects',    icon: GitBranch,       label: 'Projects'     },
  { href: '/workflows',   icon: Zap,             label: 'Workflows'    },
  { href: '/approvals',   icon: Clock,           label: 'Approvals'    },
  { href: '/agents',      icon: Cpu,             label: 'Agents'       },
  { href: '/cost',        icon: DollarSign,      label: 'Cost'         },
  { href: '/enterprise',  icon: Shield,          label: 'Enterprise'   },
  { href: '/observability',icon: BarChart3,       label: 'Observability'},
  { href: '/admin',       icon: Database,        label: 'Admin'        },
  { href: '/settings',    icon: Settings,        label: 'Settings'     },
];

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const user = getCurrentUser();

  function handleLogout() {
    document.cookie = 'cf_access_token=; Max-Age=0; path=/';
    logout();
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Cpu />
        </div>
        <div className="sidebar-logo-text">
          <span>CodeForge AI</span>
          <span>SDLC Platform</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {NAV.map(({ href, icon: Icon, label }) => (
          <button
            key={href}
            className={`nav-item${pathname === href ? ' active' : ''}`}
            onClick={() => router.push(href)}
          >
            <Icon />
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="user-avatar">
            {(user?.username?.[0] ?? 'U').toUpperCase()}
          </div>
          <div className="user-info">
            <div className="name">{user?.username ?? 'User'}</div>
            <div className="role">{user?.role ?? 'developer'}</div>
          </div>
          <button
            onClick={handleLogout}
            title="Logout"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-3)', padding: 4 }}
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
