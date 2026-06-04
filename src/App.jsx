import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Trazabilidad from "./modules/trazabilidad/Trazabilidad.jsx";
import Busqueda from "./modules/busqueda/Busqueda.jsx";
import Estadisticas from "./modules/estadisticas/Estadisticas.jsx";

import DruidaLogo from "./assets/icons/DriudaIcon.svg";
import SearchIcon from "./assets/icons/SearchIcon.svg?react";
import EstadisticasIcon from "./assets/icons/EstadisticasIcon.svg?react";
import ViticulturaIcon from "./assets/icons/ViticulturaIcon.svg?react";
import BellIcon from "./assets/icons/BellIcon.svg?react";
import ContactsIcon from "./assets/icons/ContactsIcon.svg?react";
import CheckIcon from "./assets/icons/CheckIcon.svg?react";
import CircleIcon from "./assets/icons/CircleIcon.svg?react";

const NAV = [
  { to: "/trazabilidad", label: "Trazabilidad", Icon: ViticulturaIcon },
  { to: "/buscar", label: "Búsqueda", Icon: SearchIcon },
  { to: "/estadisticas", label: "Estadísticas", Icon: EstadisticasIcon },
];

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <img className="app-logo" src={DruidaLogo} alt="Druida" />
        <div className="header-search">
          <SearchIcon />
          <input placeholder="¿Qué querés buscar?" aria-label="Buscar" readOnly />
        </div>
        <div className="user-circle">TS</div>
      </header>

      <div className="app-body">
        <nav className="sidebar">
          <button className="new-button" type="button">
            <span className="plus">+</span> Nuevo
          </button>
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `menu-link ${isActive ? "active" : ""}`}
            >
              <Icon /> {label}
            </NavLink>
          ))}
          <div className="sidebar-note">
            Showcase
            <br />
            corre offline con datos demo
          </div>
        </nav>

        <main className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/trazabilidad" replace />} />
            <Route path="/trazabilidad" element={<Trazabilidad />} />
            <Route path="/buscar" element={<Busqueda />} />
            <Route path="/estadisticas" element={<Estadisticas />} />
          </Routes>
        </main>

        <aside className="right-rail">
          <span className="rail-icon">
            <BellIcon />
            <span className="rail-badge">4</span>
          </span>
          <span className="rail-icon"><ContactsIcon /></span>
          <span className="rail-icon"><CheckIcon /></span>
          <span className="rail-icon"><CircleIcon /></span>
        </aside>
      </div>
    </div>
  );
}
