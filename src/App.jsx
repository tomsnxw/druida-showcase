import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Trazabilidad from "./modules/trazabilidad/Trazabilidad.jsx";
import Estadisticas from "./modules/estadisticas/Estadisticas.jsx";
import HeaderSearch from "./modules/busqueda/HeaderSearch.jsx";

import DruidaLogo from "./assets/icons/DriudaIcon.svg";
import EstadisticasIcon from "./assets/icons/EstadisticasIcon.svg?react";
import ViticulturaIcon from "./assets/icons/ViticulturaIcon.svg?react";
import CalendarIcon from "./assets/icons/CalendarIcon.svg?react";
import ContactsIcon from "./assets/icons/ContactsIcon.svg?react";
import CheckIcon from "./assets/icons/CheckIcon.svg?react";
import CircleIcon from "./assets/icons/CircleIcon.svg?react";

const NAV = [
  { to: "/trazabilidad", label: "Trazabilidad", Icon: ViticulturaIcon },
  { to: "/estadisticas", label: "Estadísticas", Icon: EstadisticasIcon },
];

export default function App() {
  const today = new Date();
  const todayLabel = today.toLocaleDateString("es-AR", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="app">
      <header className="app-header">
        <img className="app-logo" src={DruidaLogo} alt="Druida" />
        <HeaderSearch />
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
            <Route path="/estadisticas" element={<Estadisticas />} />
          </Routes>
        </main>

        <aside className="right-rail">
          {/* Calendar that always shows today's date number — mirrors the
              real app's quick-glance date control. */}
          <span className="rail-icon rail-calendar" title={todayLabel}>
            <CalendarIcon />
            <span className="rail-day">{today.getDate()}</span>
          </span>
          <span className="rail-icon"><ContactsIcon /></span>
          <span className="rail-icon"><CheckIcon /></span>
          <span className="rail-icon"><CircleIcon /></span>
        </aside>
      </div>
    </div>
  );
}
