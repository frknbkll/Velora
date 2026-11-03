(() => {
  const stage = document.querySelector('[data-world-map]');
  if (!stage) return;
  const control = stage.querySelector('.world-motion');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const locations = {
    rotterdam: { lat: 51.9244, lon: 4.4777, name: 'Rotterdam', description: 'Rotterdam, Netherlands — Lenora’s main establishment.' },
    paris: { lat: 48.8566, lon: 2.3522, name: 'Paris', description: 'Paris, France — Lenora establishment.' },
    london: { lat: 51.5074, lon: -.1278, name: 'London', description: 'London, United Kingdom — Lenora establishment.' },
    dubai: { lat: 25.2048, lon: 55.2708, name: 'Dubai', description: 'Dubai, United Arab Emirates — Lenora establishment.' },
    frankfurt: { lat: 50.1109, lon: 8.6821, name: 'Frankfurt', description: 'Frankfurt, Germany — Lenora establishment.' },
    turkiye: { lat: 39, lon: 35, name: 'Türkiye', description: 'Türkiye — country-level location; a specific city has not been specified.' }
  };
  const plane = stage.querySelector('.world-plane');
  const buttons = document.querySelectorAll('[data-location]');
  Object.entries(locations).forEach(([key, place]) => {
    const marker = document.createElement('span');
    marker.className = `world-pin${key === 'rotterdam' ? ' is-active' : ''}`;
    marker.dataset.pin = key;
    marker.style.left = `${(place.lon + 180) / 360 * 100}%`;
    marker.style.top = `${(90 - place.lat) / 180 * 100}%`;
    const label = document.createElement('span');
    label.textContent = place.name;
    marker.append(label);
    plane.append(marker);
  });
  buttons.forEach(button => button.addEventListener('click', () => {
    const key = button.dataset.location;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    stage.querySelectorAll('[data-pin]').forEach(pin => pin.classList.toggle('is-active', pin.dataset.pin === key));
    document.querySelector('.world-selection').textContent = locations[key].description;
  }));
  let paused = reduced.matches;
  const reset = () => {
    stage.style.removeProperty('--atlas-x');
    stage.style.removeProperty('--atlas-z');
  };
  const sync = () => {
    stage.classList.toggle('is-paused', paused);
    control.setAttribute('aria-pressed', String(paused));
    control.innerHTML = paused ? 'Enable effects <span aria-hidden="true">&#9655;</span>' : 'Pause effects <span aria-hidden="true">&#8545;</span>';
    reset();
  };
  control.addEventListener('click', () => { paused = !paused; sync(); });
  reduced.addEventListener('change', () => { paused = reduced.matches; sync(); });
  stage.addEventListener('pointermove', (event) => {
    if (paused || event.pointerType === 'touch') return;
    const rect = stage.getBoundingClientRect();
    stage.style.setProperty('--atlas-x', `${23 + ((event.clientY - rect.top) / rect.height - .5) * -10}deg`);
    stage.style.setProperty('--atlas-z', `${-6 + ((event.clientX - rect.left) / rect.width - .5) * 5}deg`);
  });
  stage.addEventListener('pointerleave', reset);
  sync();
})();
