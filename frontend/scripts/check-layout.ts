/**
 * Invariants for the diagram layout maths.
 *
 *   yarn check:layout
 *
 * The frontend carries no test runner, and adding one for a single module was
 * not worth the dependency — but diagram layout is the one place in this
 * codebase where the frontend does real arithmetic, and "it looked right in
 * the browser" is not a claim about a 3-4-5 triangle actually being right.
 * esbuild already ships with Vite, so this bundles and runs on plain node.
 *
 * Every assertion below is a property rather than a snapshot: an angle sum, a
 * monotone curve, a parent centred over its children. Those survive a change
 * to spacing or margins, which a pinned coordinate would not.
 */

import {
  layoutGraph, triangleFromSides, rectangleFromSides, regularPolygon,
  fitPoints, interiorAngles, sampleSeries, resolveYRange, makeScale, VIEW,
} from '../src/components/diagram/layout'

let fails = 0
const ok = (name: string, cond: boolean, detail = '') => {
  console.log(`${cond ? '  PASS' : '  FAIL'}  ${name}${detail && !cond ? ` -> ${detail}` : ''}`)
  if (!cond) fails++
}
const g = (layout: any, nodes: string[], edges: [string, string][]) => ({
  kind: 'graph', layout, id: 'x', title: 't', caption: 'c', steps: [],
  nodes: nodes.map((id) => ({ id, label: id, tone: 'neutral' })),
  edges: edges.map(([from, to]) => ({ from, to, label: null, directed: true })),
}) as any

console.log('\n=== geometry ===')
const tri = fitPoints(triangleFromSides([3, 4, 5]))
const angles = interiorAngles(tri)
ok('3-4-5 has a 90-degree angle', angles.some((a) => Math.abs(a - 90) < 0.5), angles.map(a=>a.toFixed(1)).join(','))
ok('triangle angles sum to 180', Math.abs(angles.reduce((s, a) => s + a, 0) - 180) < 0.5)
ok('triangle fits the viewBox', tri.every((p) => p.x >= -0.01 && p.x <= VIEW + 0.01 && p.y >= -0.01 && p.y <= VIEW + 0.01))
const hex = interiorAngles(fitPoints(regularPolygon(6)))
ok('regular hexagon angles are 120', hex.every((a) => Math.abs(a - 120) < 0.5), hex.map(a=>a.toFixed(1)).join(','))
const rect = interiorAngles(fitPoints(rectangleFromSides([4, 2])))
ok('rectangle angles are 90', rect.every((a) => Math.abs(a - 90) < 0.5))
ok('flat shape does not produce NaN', fitPoints([{x:0,y:0},{x:5,y:0}]).every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)))

console.log('\n=== graph layouts ===')
const chain = layoutGraph(g('chain', ['a','b','c'], [['a','b'],['b','c']]))
ok('chain follows edge order, not array order', chain.map((n) => n.id).join(',') === 'a,b,c', chain.map(n=>n.id).join(','))
ok('chain of 3 is horizontal', new Set(chain.map((n) => Math.round(n.y))).size === 1)
const chainStart = layoutGraph(g('chain', ['c','a','b'], [['a','b'],['b','c']]))
ok('chain finds the real start when nodes are out of order', chainStart[0].id === 'a', chainStart.map(n=>n.id).join(','))
ok('chain of 6 goes vertical', new Set(layoutGraph(g('chain', ['a','b','c','d','e','f'], [['a','b'],['b','c'],['c','d'],['d','e'],['e','f']])).map((n) => Math.round(n.x))).size === 1)

const tree = layoutGraph(g('tree', ['r','l','rr','ll','lr'], [['r','l'],['r','rr'],['l','ll'],['l','lr']]))
const at = (id: string) => tree.find((n) => n.id === id)!
ok('tree root is above its children', at('r').y < at('l').y && at('r').y < at('rr').y)
ok('tree leaves at one depth share a row', Math.abs(at('ll').y - at('lr').y) < 0.01)
ok('tree parent is centred over its children', Math.abs(at('l').x - (at('ll').x + at('lr').x) / 2) < 0.01)
ok('tree children keep declared order left to right', at('ll').x < at('lr').x && at('l').x < at('rr').x)
ok('tree fits the viewBox', tree.every((n) => n.x >= 0 && n.x <= VIEW && n.y >= 0 && n.y <= VIEW))

const layered = layoutGraph(g('layered', ['a','b','c','d'], [['a','b'],['a','c'],['b','d'],['c','d']]))
const la = (id: string) => layered.find((n) => n.id === id)!
ok('layered ranks by longest path', la('a').y < la('b').y && la('b').y < la('d').y)
ok('layered puts siblings on one rank', Math.abs(la('b').y - la('c').y) < 0.01)
const cyclic = layoutGraph(g('layered', ['a','b','c'], [['a','b'],['b','c'],['c','a']]))
ok('a cycle still places every node', cyclic.length === 3 && cyclic.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y)))
ok('circular places all nodes on one radius', (() => {
  const c = layoutGraph(g('circular', ['a','b','c','d','e'], []))
  const r = c.map((n) => Math.hypot(n.x - VIEW/2, n.y - VIEW/2))
  return Math.max(...r) - Math.min(...r) < 0.01
})())
const orphan = layoutGraph(g('tree', ['r','a','lonely'], [['r','a']]))
ok('a disconnected node is still placed', orphan.length === 3 && orphan.every((n) => Number.isFinite(n.x)))

console.log('\n=== plots ===')
const sig = sampleSeries({ id:'s', label:'s', tone:'brand', type:'function', fn:{family:'sigmoid',params:{k:1}}, points:null } as any, [-6, 6])
ok('sigmoid is monotone increasing', sig.every((p, i) => i === 0 || p.y >= sig[i-1].y))
ok('sigmoid(0) = 0.5', Math.abs(sig.find((p) => Math.abs(p.x) < 0.07)!.y - 0.5) < 0.02)
ok('sigmoid stays in 0..1', sig.every((p) => p.y >= 0 && p.y <= 1))
const exp = sampleSeries({ id:'e', label:'e', tone:'brand', type:'function', fn:{family:'exponential',params:{k:200}}, points:null } as any, [-6, 6])
ok('overflowing exponential drops non-finite points', exp.every((p) => Number.isFinite(p.y)), `${exp.length} pts`)
const norm = sampleSeries({ id:'n', label:'n', tone:'brand', type:'function', fn:{family:'normal',params:{mu:0,sigma:1}}, points:null } as any, [-4, 4])
ok('normal peaks at the mean', Math.abs(norm.reduce((a, b) => (b.y > a.y ? b : a)).x) < 0.1)
ok('auto y-range brackets the data', (() => {
  const [lo, hi] = resolveYRange(null, [norm])
  return lo <= Math.min(...norm.map(p=>p.y)) && hi >= Math.max(...norm.map(p=>p.y))
})())
ok('flat series gets a non-zero y-range', (() => { const [lo,hi] = resolveYRange(null, [[{x:0,y:5},{x:1,y:5}]]); return hi > lo })())
const scale = makeScale([-6, 6], [0, 1])
ok('scale flips y (data max is view min)', scale({x:0,y:1}).y < scale({x:0,y:0}).y)
ok('scaled points stay in the viewBox', sig.map(scale).every((p) => p.x >= 0 && p.x <= VIEW && p.y >= 0 && p.y <= VIEW))

console.log(`\n${fails === 0 ? 'ALL PASS' : `${fails} FAILED`}\n`)
process.exit(fails === 0 ? 0 : 1)
