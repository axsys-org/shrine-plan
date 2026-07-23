const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const configuration = JSON.parse(fs.readFileSync(path.join(root, 'language-configuration.json'), 'utf8'));
const grammar = JSON.parse(fs.readFileSync(path.join(root, 'syntaxes/foil.tmLanguage.json'), 'utf8'));

if (manifest.contributes.languages[0].extensions[0] !== '.foil') {
  throw new Error('The extension must register .foil files');
}
if (grammar.scopeName !== 'source.foil') {
  throw new Error('Unexpected grammar scope');
}

for (const rule of Object.values(grammar.repository)) {
  for (const pattern of rule.patterns || []) {
    if (pattern.match) new RegExp(pattern.match, 'm');
  }
}
new RegExp(configuration.wordPattern);
for (const pattern of Object.values(configuration.indentationRules)) new RegExp(pattern);

console.log(`Validated ${manifest.displayName} ${manifest.version}`);
