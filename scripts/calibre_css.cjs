// Execute Calibre's own bundled CSS rules without a graphical WebEngine page.
// The trusted helper supplies the two pinned SDK scripts, never document code.
const vm = require('node:vm');
const {performance} = require('node:perf_hooks');

async function main(input) {
  const request = JSON.parse(input);
  let complete;
  const document = {};
  const context = vm.createContext({document, performance, setTimeout, clearTimeout,
    console: {log:()=>{}, warn:()=>{}, error:()=>{}}});
  context.window = context;
  context.self = context;
  Object.defineProperty(document, 'title', {set(value) {
    if (String(value).startsWith('checked:') && complete) {
      const resolve = complete; complete = null;
      resolve(context.get_css_results());
    }
  }});
  for (const [name, source] of request.scripts) vm.runInContext(source, context, {filename:name, timeout:30000});
  const results = [];
  for (const source of request.sources) {
    const result = await new Promise(resolve => {
      complete = resolve;
      context.check_css(source, Boolean(request.fix), request.disabled_rules || []);
    });
    if (result.length !== 1) throw new Error('Unexpected native CSS result count');
    results.push(result[0]);
  }
  return results;
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {input += chunk;});
process.stdin.on('end', () => main(input).then(value => {
  process.stdout.write(JSON.stringify(value));
}).catch(error => {process.stderr.write(String(error.stack || error));process.exitCode=1;}));
