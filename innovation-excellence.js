/* Reveal deep-linked workshop disclosures. Shared navigation lives in site.js. */
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
