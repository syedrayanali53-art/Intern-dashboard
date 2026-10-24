const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = {window:{}};
const source=fs.readFileSync(path.join(__dirname, '../intern-hunt.html'), 'utf8');
vm.runInNewContext(source.match(/<script id="eligibility">([\s\S]*?)<\/script>/)[1], context);
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'eligibility_cases.json'), 'utf8'));
for (const c of cases) {
  const result = context.window.InternEligibility.classify(c.record);
  assert.equal(result.sponsorship_state, c.state, c.name + ' state');
  assert.equal(result.sponsorship_checked, c.checked, c.name + ' checked');
  assert.equal(result.citizenship_required, c.citizenship, c.name + ' citizenship');
}
console.log('PASS: ' + cases.length + ' posting eligibility cases');
