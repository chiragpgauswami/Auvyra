import {
  BarChart2,
  Brain,
  LayoutDashboard,
  Lightbulb,
  PlaySquare,
  Send,
  Settings,
  Tv,
  Video,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
}

const navItems = [
  { name: "Dashboard", path: "/", icon: LayoutDashboard },
  { name: "Channels", path: "/channels", icon: Tv },
  { name: "AI Brain", path: "/brain", icon: Brain },
  { name: "Research", path: "/research", icon: Lightbulb },
  { name: "Create", path: "/create", icon: Video },
  { name: "Videos", path: "/videos", icon: PlaySquare },
  { name: "Publishing", path: "/publishing", icon: Send },
  { name: "Analytics", path: "/analytics", icon: BarChart2 },
  { name: "Settings", path: "/settings", icon: Settings },
];

const Sidebar = ({ isOpen, setIsOpen }: SidebarProps) => {
  return (
    <>
      <div
        className={`fixed inset-0 bg-slate-900/80 z-20 lg:hidden ${isOpen ? "block" : "hidden"}`}
        onClick={() => setIsOpen(false)}
      />
      <div
        className={`fixed lg:static inset-y-0 left-0 z-30 w-64 bg-slate-900 border-r border-slate-800 transform transition-transform duration-200 ease-in-out ${isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"} flex flex-col`}
      >
        <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800">
          <span className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
            Auvyra
          </span>
          <button
            className="lg:hidden text-slate-400 hover:text-white"
            onClick={() => setIsOpen(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.name}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? "bg-primary-900/50 text-primary-400"
                      : "text-slate-400 hover:text-slate-50 hover:bg-slate-800"
                  }`
                }
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>
    </>
  );
};

export default Sidebar;
