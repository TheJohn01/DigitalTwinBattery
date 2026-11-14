// Sets data-dew="dark" (Dusk) or "light" (Daylight) on the html element from the text colour
// Streamlit gives the app (light text = dark theme), so dewpoint.css can switch tokens; CSS
// alone cannot see which theme is active. No less-than signs in this file: the sanitiser
// drops such scripts.
// shortcut: polls twice a second; upgrade to a theme event if Streamlit adds one (issue #11920).
if (!window.dewThemeWatch) {
  const mark = () => {
    const app = document.querySelector(".stApp");
    if (!app) return;
    const [r, g, b] = getComputedStyle(app).color.match(/\d+/g).map(Number);
    document.documentElement.dataset.dew = (r + g + b) / 3 > 128 ? "dark" : "light";
  };
  mark();
  window.dewThemeWatch = setInterval(mark, 500);
}
