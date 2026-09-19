const $ = s => document.querySelector(s);
const root = document.documentElement;
root.classList.add('js');

const header = $('#siteHeader');
let queued = false;
addEventListener('scroll', () => {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => {
    header.classList.toggle('lifted', scrollY > 140);
    root.classList.toggle('scrolled', scrollY > innerHeight * 0.55);
    queued = false;
  });
}, { passive: true });

// fade sections in as they arrive. the negative margins stop it firing while the
// thing is still half off screen, which looked jumpy on a trackpad
const watcher = new IntersectionObserver((entries, obs) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    e.target.classList.add('in');
    obs.unobserve(e.target);
  }
}, { rootMargin: '-8% 0px -12%' });
document.querySelectorAll('.reveal').forEach((el, i) => {
  el.style.transitionDelay = (i % 3) * 90 + 'ms'; // stagger in threes
  watcher.observe(el);
});

let toastTimer;

function toast(msg) {
  let el = $('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  el.textContent = msg;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 3200);
}
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-soon]');
  if (!btn) return;
  e.preventDefault();
  toast(btn.dataset.soon + ' is not built yet. This page is a design preview.');
});

// settings live on <html> as data attributes, css does the rest
const controls = document.querySelectorAll('.a11y input[name]');
const defaults = { motion: 'auto', contrast: 'normal', font: 'normal', decor: 'on' };
let prefs = { ...defaults };
try { Object.assign(prefs, JSON.parse(localStorage.getItem('lodestone-a11y') || '{}')); } catch { } // private windows throw

function apply() {
  root.dataset.motion = prefs.motion;
  root.dataset.contrast = prefs.contrast;
  root.dataset.font = prefs.font;
  root.dataset.decor = prefs.decor;
  controls.forEach(i => i.checked = i.value === prefs[i.name]);
  try { localStorage.setItem('lodestone-a11y', JSON.stringify(prefs)); } catch { }
  leaves.sync();
}
controls.forEach(i => i.addEventListener('change', () => {
  prefs[i.name] = i.type === 'checkbox' && !i.checked ? defaults[i.name] : i.value;
  apply();
}));
$('#a11yReset').addEventListener('click', () => { prefs = { ...defaults }; apply(); toast('Accessibility settings reset.'); });
$('#a11yOpen').addEventListener('click', () => $('#a11y').showModal());

// leaves. numbers here are all eyeballed, do not read anything into them
const leaves = (() => {
  const canvas = $('#leaves'), ctx = canvas.getContext('2d');
  const stillPlease = matchMedia('(prefers-reduced-motion: reduce)');
  const tints = ['#B85C27', '#D58A35', '#6E3026', '#8E4A22', '#4B523B'];
  let flock = [], raf = 0, wind = 0, gustAt = 0, last = 0, scale = 1;

  const allowed = () => prefs.decor !== 'off' &&
    (prefs.motion === 'full' || (prefs.motion === 'auto' && !stillPlease.matches));

  function leaf(fromTop) {
    // TODO: leaves keep spawning behind the header, not enough to bother fixing yet
    return {
      x: Math.random() * innerWidth,
      y: fromTop ? -40 : Math.random() * innerHeight,
      size: 9 + Math.random() * 13,
      fall: 22 + Math.random() * 36,
      spin: (Math.random() - 0.5) * 1.4,
      angle: Math.random() * Math.PI * 2,
      sway: 0.5 + Math.random() * 1.1,
      phase: Math.random() * Math.PI * 2,
      tint: tints[(Math.random() * tints.length) | 0],
      alpha: 0.4 + Math.random() * 0.45,
    };
  }

  function resize() {
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(innerWidth * dpr);
    canvas.height = Math.round(innerHeight * dpr);
    canvas.style.width = innerWidth + 'px';
    canvas.style.height = innerHeight + 'px';
    scale = dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = innerWidth < 700 ? 10 : innerWidth < 1200 ? 18 : 26;
    while (flock.length < count) flock.push(leaf(false));
    flock.length = count;
  }

  function shape(half) {
    ctx.beginPath();
    ctx.moveTo(0, -half);
    ctx.quadraticCurveTo(half, 0, 0, half);
    ctx.quadraticCurveTo(-half, 0, 0, -half);
    ctx.fill();
  }

  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.05) || 0.016;
    last = now;

    //wind leaf animation without this falls straight
    if (now > gustAt) {
      wind = (Math.random() < 0.5 ? -1 :1) * (14 + Math.random() * 30);
      gustAt = now + 6000 + Math.random() * 9000;
    }
    wind *= 0.99;

    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const l of flock) {
      l.angle += dt * l.sway;
      l.angle += l.spin * dt;
      l.y += l.fall * dt;
      l.x += (wind + Math.sin(l.phase) * 20) * dt;
      l.phase += dt;

      if (l.y - l.size > innerHeight) Object.assign(l, leaf(true));
      if (l.x < -60) l.x = innerWidth + 50;
      if (l.x > innerWidth +60) l.x = -50;

      const squash = 0.55 + 0.45 * Math.abs(Math.cos(l.phase));
      const cos = Math.cos(l.angle), sin = Math.sin(l.angle);
      ctx.setTransform(cos * scale, sin * scale, -sin * squash * scale, cos * squash * scale, l.x * scale, l.y * scale);
      ctx.globalAlpha = l.alpha;
      ctx.fillStyle = l.tint;
      shape(l.size / 2);
    }
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(frame);
  }
  
  function sync() {
    cancelAnimationFrame(raf);
    raf = 0;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    if (!allowed()) return;
    resize();
    last = performance.now();
    gustAt = last + 2500;
    raf = requestAnimationFrame(frame);
  }

  addEventListener('resize', () => { if (allowed()) resize(); });

  document.addEventListener('visibilitychange', () => document.hidden ? cancelAnimationFrame(raf) : sync());
  stillPlease.addEventListener('change', () => sync());
  return { sync };
})();

apply();