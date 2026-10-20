/* Review-page navigation and hash links. No analytics, storage or form submission. */
const menuButton = document.querySelector('.ie-menu-toggle');
const navigation = document.querySelector('#page-navigation');

function closeMenu() {
  if (!menuButton || !navigation) return;
  menuButton.setAttribute('aria-expanded', 'false');
  navigation.classList.remove('ie-is-open');
}

menuButton?.addEventListener('click', () => {
  const next = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(next));
  navigation?.classList.toggle('ie-is-open', next);
});

navigation?.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menuButton?.getAttribute('aria-expanded') === 'true') {
    closeMenu();
    menuButton.focus();
  }
});

window.matchMedia('(min-width: 801px)').addEventListener('change', closeMenu);


// A direct workshop link reveals its stage. Other stages remain independent.
function revealLinkedStage(hash) {
  if (!hash || hash.length < 2) return;
  let id;
  try { id = decodeURIComponent(hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target) return;
  let node = target;
  while (node) {
    if (node instanceof HTMLDetailsElement) node.open = true;
    node = node.parentElement;
  }
}
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', () => revealLinkedStage(link.getAttribute('href')));
});
window.addEventListener('hashchange', () => revealLinkedStage(window.location.hash));
revealLinkedStage(window.location.hash);
