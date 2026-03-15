window.t = (key, vars = {}) => {
  let str = (window.TRANSLATIONS || {})[key] || key;
  Object.entries(vars).forEach(([k, v]) => {
    str = str.replaceAll(`{${k}}`, String(v));
  });
  return str;
};
