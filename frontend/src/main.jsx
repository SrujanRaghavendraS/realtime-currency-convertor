import React from 'react';
import ReactDOM from 'react-dom/client';
import Dashboard from './pages/Dashboard.jsx';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';
import './styles/explainers.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Dashboard />
  </React.StrictMode>
);
