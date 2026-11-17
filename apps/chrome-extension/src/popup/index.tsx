import React from 'react';
import ReactDOM from 'react-dom/client';
import { Popup } from './Popup.js';

// pi-lens-ignore: no-non-null-assertion — popup.html guarantees #popup-root
ReactDOM.createRoot(document.getElementById('popup-root')!).render(
  <React.StrictMode>
    <Popup />
  </React.StrictMode>
);
