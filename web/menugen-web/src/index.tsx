import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { applySkin, getStoredSkin } from './theme/skins'; // MG_SKIN

// MG_SKIN: применяем сохранённый скин до первого рендера (без вспышки).
applySkin(getStoredSkin());

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(<React.StrictMode><App /></React.StrictMode>);
