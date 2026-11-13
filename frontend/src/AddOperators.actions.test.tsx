import {isValidElement, type ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
import {AddOperators} from './AddOperators';
import {api} from './api';
import type {Graph} from './types';

const hooks=vi.hoisted(()=>({values:[] as unknown[], cursor:0}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:()=>{},useRef:()=>({current:null}),useState:(initial:unknown)=>{
  const i=hooks.cursor++; if(!(i in hooks.values))hooks.values[i]=initial;
  return [hooks.values[i],(next:unknown)=>{hooks.values[i]=typeof next==='function'?next(hooks.values[i]):next;}];
}}));
vi.mock('./api',()=>({api:{workflows:vi.fn(),importWorkflow:vi.fn(),importRouteArchive:vi.fn(),importRouteCollection:vi.fn(),saveWorkflow:vi.fn(),registerRoutes:vi.fn()}}));
const onChanged=vi.fn(async()=>{}),onPending=vi.fn(),onError=vi.fn(),onMessage=vi.fn();
type Element={type:unknown;props:Record<string,unknown>};
function elements(node:ReactNode):Element[] {
  if(Array.isArray(node))return node.flatMap(elements);
  if(!isValidElement<Record<string,unknown>>(node))return [];
  return [node,...elements(node.props.children as ReactNode)];
}
function render(){hooks.cursor=0;return AddOperators({state:{generation:null,packages:[],descriptors:[]},busy:false,onChanged,onPending,onError,onMessage,onPackage:()=>{},onRefresh:()=>{}});}
function triggerFiles(files: unknown[]) {
  const field=elements(render()).find(n=>n.type==='input'&&n.props.type==='file')!;
  (field.props.onChange as Function)({target:{files,value:'fake'}});
}
function triggerCollection(files: unknown[]) {
  const field=elements(render()).filter(n=>n.type==='input'&&n.props.type==='file')[1]!;
  (field.props.onChange as Function)({target:{files,value:'fake'}});
}
const graph:Graph={schema_version:2,name:'Imported',base_dir:'.',nodes:[],edges:[],memory:{enabled:true}};
beforeEach(()=>{hooks.values=[];hooks.cursor=0;vi.clearAllMocks();vi.mocked(api.workflows).mockResolvedValue([]);
  vi.mocked(api.saveWorkflow).mockResolvedValue({id:'saved',version:1,graph,updated_at:''});vi.mocked(api.registerRoutes).mockResolvedValue([]);});
it.each(['route.operon.zip', 'route.operon', 'route.OPERON'])('imports %s, saves its graph and registers it without opening or running a canvas',async name=>{
  vi.mocked(api.importWorkflow).mockResolvedValue(graph);
  const file=new File([new Uint8Array([80,75,3,4])],name);triggerFiles([file]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.importWorkflow).toHaveBeenCalledWith(file);expect(vi.mocked(api.saveWorkflow).mock.calls[0][0]).toMatchObject(graph);
  expect(api.registerRoutes).toHaveBeenCalledWith(['saved']);expect(onChanged).toHaveBeenCalledOnce();
});
it('accepts only single route bundles in the route file picker',()=>{
  const field=elements(render()).find(n=>n.type==='input'&&n.props.type==='file')!;
  expect(String(field.props.accept)).toBe('.operon.zip');
});
it('keeps successfully saved imports selected when a later file fails',async()=>{
  triggerFiles([{name:'one.json',text:async()=>JSON.stringify(graph)},{name:'bad.json',text:async()=>'{broken'}]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(hooks.values[1]).toEqual(['saved']);expect(api.registerRoutes).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalled();expect(onChanged).toHaveBeenCalledOnce();
});
it('registers all selected saved workflows in a single request',async()=>{
  hooks.values=[[],['one','two'],'',false];
  const button=elements(render()).find(n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children.includes('添加到算子库'))!;
  expect(button.props.disabled).toBe(false);(button.props.onClick as Function)();
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.registerRoutes).toHaveBeenCalledExactlyOnceWith(['one','two']);expect(api.saveWorkflow).not.toHaveBeenCalled();
});
it('reports a rejected workflow without clearing its selection or claiming success',async()=>{
  hooks.values=[[],['incomplete'],'',false];
  vi.mocked(api.registerRoutes).mockRejectedValue(new Error('PCA needs 1 input.'));
  const button=elements(render()).find(n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children.includes('添加到算子库'))!;
  (button.props.onClick as Function)();
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(onError).toHaveBeenLastCalledWith('路线未添加：PCA needs 1 input. 请先导入与路线同版本的算子库后重试。');
  expect(hooks.values[1]).toEqual(['incomplete']);
  expect(onMessage).not.toHaveBeenCalledWith('路线算子已添加，即刻可用。');
  expect(onChanged).toHaveBeenCalledOnce();
});

it('imports one route collection archive through a single request',async()=>{
  vi.mocked(api.importRouteArchive).mockResolvedValue({routes: [], failed: []});
  const file=new File([new Uint8Array([80,75,3,4])],'routes.zip');
  triggerFiles([file]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.importRouteArchive).toHaveBeenCalledWith(file);
  expect(api.importWorkflow).not.toHaveBeenCalled();
  expect(api.registerRoutes).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenCalledWith('路线算子已添加，即刻可用。');
});
it('rejects a collection mixed with individual route files',async()=>{
  triggerFiles([new File([new Uint8Array([80,75,3,4])],'routes.zip'),new File(['{}'],'one.json')]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(onError).toHaveBeenCalledWith('路线压缩包请单独上传。');
  expect(api.importRouteArchive).not.toHaveBeenCalled();
});

it('imports a route library collection through the 5.0.0 endpoint',async()=>{
  vi.mocked(api.importRouteCollection).mockResolvedValue({count:2,names:['Alpha','Beta'],failed:[]});
  const file=new File([new Uint8Array([80,75,3,4])],'operon-routes-v0.0.0.zip');
  triggerCollection([file]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.importRouteCollection).toHaveBeenCalledWith(file);
  expect(api.importRouteArchive).not.toHaveBeenCalled();
  expect(onMessage).toHaveBeenLastCalledWith('已导入 2 条路线：Alpha, Beta');
  expect(onChanged).toHaveBeenCalledOnce();
});
it('keeps a pin-mismatch detail verbatim when the collection is rejected',async()=>{
  const detail='Route "Alpha" pins operon.scale at code_sha 11111111, installed code_sha 22222222.';
  vi.mocked(api.importRouteCollection).mockRejectedValue(new Error(detail));
  triggerCollection([new File([new Uint8Array([80,75,3,4])],'operon-routes-v0.0.0.zip')]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(onError).toHaveBeenLastCalledWith(detail);
  expect(onMessage).not.toHaveBeenCalledWith(expect.stringContaining('已导入'));
});
it('asks for an operon-routes-v0.0.x collection when another ZIP is chosen',async()=>{
  triggerCollection([new File([new Uint8Array([80,75,3,4])],'routes.zip')]);
  expect(api.importRouteCollection).not.toHaveBeenCalled();
  expect(onError).toHaveBeenLastCalledWith('路线库请选择 operon-routes-v0.0.x.zip（包含 routes/*.operon.zip）。');
});
