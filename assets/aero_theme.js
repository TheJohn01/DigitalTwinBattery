// Sets data-aero="dark" or "light" on the html element from the text colour Streamlit gives
// the app (light text = dark theme), so aero.css can switch looks; CSS alone cannot see
// which theme is active. No less-than signs in this file: the sanitiser drops such scripts.
// shortcut: polls twice a second; upgrade to a theme event if Streamlit adds one (issue #11920).
if (!window.aeroThemeWatch) {
  const mark = () => {
    const app = document.querySelector(".stApp");
    if (!app) return;
    const [r, g, b] = getComputedStyle(app).color.match(/\d+/g).map(Number);
    document.documentElement.dataset.aero = (r + g + b) / 3 > 128 ? "dark" : "light";
  };
  mark();
  window.aeroThemeWatch = setInterval(mark, 500);
}
