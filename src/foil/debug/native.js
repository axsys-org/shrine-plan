// Fail before any application binding. Native pages never enhance a legacy
// document or manufacture a replacement UI when the declaration is missing.
if (!document.querySelector('[data-grove-contract="debugger/v1"]')) {
  throw new Error('Grove debugger declaration missing. Start Eden with --debug; use /ns for the legacy explorer.');
}
void import('./workbench.js');
