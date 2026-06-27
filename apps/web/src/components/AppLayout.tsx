import Sidebar from './Sidebar';
import Topbar from './Topbar';

interface LayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}

export default function AppLayout({ children, title, subtitle }: LayoutProps) {
  return (
    <div className="layout">
      <Sidebar />
      <div className="main">
        <Topbar title={title} subtitle={subtitle} />
        <div className="page-content">{children}</div>
      </div>
    </div>
  );
}
