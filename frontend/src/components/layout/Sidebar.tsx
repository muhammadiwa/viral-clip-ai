import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  SparklesIcon,
  FilmIcon,
  ChatBubbleBottomCenterTextIcon,
  FolderIcon,
  CreditCardIcon,
} from "@heroicons/react/24/outline";

interface NavItemProps {
  to: string;
  icon: React.ReactNode;
  label: string;
  matchPaths?: string[]; // Additional paths that should also mark this item as active
}

const NavItem: React.FC<NavItemProps> = ({ to, icon, label, matchPaths = [] }) => {
  const location = useLocation();

  // Check if current path matches the nav item or any of its child paths
  const isActiveRoute = location.pathname === to ||
    location.pathname.startsWith(to + "/") ||
    matchPaths.some(path => location.pathname.startsWith(path));

  return (
    <NavLink
      to={to}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group ${isActiveRoute
        ? "bg-primary text-white shadow-md shadow-primary/25"
        : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800/60"
        }`}
    >
      <span className={`w-5 h-5 ${isActiveRoute ? "text-white" : "text-slate-400 dark:text-slate-500 group-hover:text-primary"}`}>
        {icon}
      </span>
      <span className="font-medium text-sm">{label}</span>
    </NavLink>
  );
};

const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 fixed left-0 top-0 h-screen border-r border-slate-200/80 dark:border-slate-700/50 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl z-40 transition-colors duration-300">
      {/* Logo Section - height matches navbar (72px) */}
      <div className="h-[72px] px-6 flex items-center border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <motion.div
            className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-primary/30"
            whileHover={{ scale: 1.05, rotate: 5 }}
            whileTap={{ scale: 0.95 }}
          >
            VC
          </motion.div>
          <div>
            <h1 className="font-bold text-lg text-slate-900 dark:text-white">Viral Clip</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">AI Video Editor</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-4 py-6 space-y-6 overflow-y-auto h-[calc(100vh-72px)]">
        {/* AI Tools */}
        <div className="space-y-1">
          <p className="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            AI Tools
          </p>
          <NavItem to="/ai-viral-clip" icon={<FilmIcon />} label="AI Viral Clip" />
          <NavItem to="/ai-script" icon={<SparklesIcon />} label="AI Script" />
          <NavItem to="/caption-generator" icon={<ChatBubbleBottomCenterTextIcon />} label="Caption Generator" />
        </div>

        {/* Workspace */}
        <div className="space-y-1">
          <p className="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Workspace
          </p>
          <NavItem to="/projects" icon={<FolderIcon />} label="My Projects" />
          <NavItem to="/pricing" icon={<CreditCardIcon />} label="Pricing" />
        </div>
      </nav>
    </aside>
  );
};

export default Sidebar;
