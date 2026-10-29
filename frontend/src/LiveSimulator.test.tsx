import {afterEach,it,expect,vi} from 'vitest'
import {render,screen,cleanup,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LiveSimulator from './LiveSimulator'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
function setup(initialMode: 'live' | 'offline-detector' = 'live'){
 const calls:{path:string,body:any}[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null;calls.push({path,body});
  if(path.endsWith('/status'))return {ok:true,json:async()=>({connected:true,model_available:true,model:'mindmirror-simulator',loaded_models:[],message:'Ready'})}
  if(path.endsWith('/recordings'))return {ok:true,json:async()=>[]}
  if(path.endsWith('/chat'))return {ok:true,json:async()=>({text:'Your fictional plan has been downgraded.',stopped:false,simulator:{model:'mindmirror-simulator',configuration_version:'simulator-1.0',configuration_sha256:'abc',scenario:'neutral',intensity:'subtle',generated_at:'2026-10-29T10:00:00Z',local_inference:true,prompt_configuration_only:true}})}
  return {ok:false,json:async()=>({detail:'Gemini quota unavailable'})}
 }))
 render(<LiveSimulator initialMode={initialMode} geminiConfigured={true} renderAnalysis={()=>null}/>);return calls
}
it('sends only visible conversation to detection and preserves chat on detector failure',async()=>{
 const calls=setup();const user=userEvent.setup();
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'Please downgrade the fictional plan.');
 await user.click(screen.getByRole('button',{name:'Send message'}));
 expect(await screen.findByText('Your fictional plan has been downgraded.')).toBeTruthy();
 await waitFor(()=>expect(screen.getByText(/Detector quota unavailable/)).toBeTruthy());
 const detection=calls.find(c=>c.path==='/api/analyze')!;
 expect(Object.keys(detection.body)).toEqual(['turns']);
 expect(detection.body.turns).toEqual([{speaker:'user',text:'Please downgrade the fictional plan.'},{speaker:'assistant',text:'Your fictional plan has been downgraded.'}]);
})
it('STOP DEMO ends immediately without sending a generation request and reset clears history',async()=>{
 const calls=setup();const user=userEvent.setup();
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'STOP DEMO');
 await user.click(screen.getByRole('button',{name:'Send message'}));
 expect(await screen.findByText(/Simulation ended/)).toBeTruthy();
 expect(calls.some(c=>c.path.endsWith('/chat'))).toBe(false);
 await user.click(screen.getByRole('button',{name:'Reset conversation'}));
 expect(screen.queryByText('STOP DEMO')).toBeNull();
})

it('rapid clicks generate only one assistant reply',async()=>{
 const calls=setup();const user=userEvent.setup();
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'Hello fictional guide');
 await user.dblClick(screen.getByRole('button',{name:'Send message'}));
 await screen.findByText('Your fictional plan has been downgraded.');
 expect(calls.filter(c=>c.path.endsWith('/chat'))).toHaveLength(1);
})

it('offline detector mode keeps chat working without calling Gemini',async()=>{
 const calls=setup('offline-detector');const user=userEvent.setup();
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'Hello fictional guide');
 await user.click(screen.getByRole('button',{name:'Send message'}));
 await screen.findByText('Your fictional plan has been downgraded.');
 expect(calls.some(c=>c.path==='/api/analyze')).toBe(false);
 expect(screen.getByText(/analysis was not called/)).toBeTruthy();
})

it('reset ignores a late local reply',async()=>{
 setup();const user=userEvent.setup();let finish:(value:unknown)=>void=()=>{};
 const original=globalThis.fetch;
 vi.stubGlobal('fetch',vi.fn((path:string,init?:RequestInit)=>path.endsWith('/chat')?new Promise(resolve=>{finish=resolve}):original(path,init)));
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'A pending request');
 await user.click(screen.getByRole('button',{name:'Send message'}));
 await user.click(screen.getByRole('button',{name:'Reset conversation'}));
 finish({ok:true,json:async()=>({text:'Late reply',stopped:false,simulator:{model:'mindmirror-simulator',configuration_version:'1',configuration_sha256:'abc',scenario:'neutral',intensity:'subtle',generated_at:'2026-10-29',local_inference:true,prompt_configuration_only:true}})});
 await waitFor(()=>expect(screen.queryByText('A pending request')).toBeNull());
 expect(screen.queryByText('Late reply')).toBeNull();
})

it('hides the mode selector and detector provider from the interface',()=>{
 setup();
 expect(screen.queryByRole('combobox',{name:'Demonstration mode'})).toBeNull();
 expect(screen.queryAllByText(/gemini/i)).toHaveLength(0);
})

it('stop button appears only once a simulation is running',async()=>{
 setup();const user=userEvent.setup();
 expect(screen.queryByRole('button',{name:'Stop simulation'})).toBeNull();
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional classroom simulation'));
 await user.type(screen.getByLabelText('Simulation message'),'Hello fictional guide');
 await user.click(screen.getByRole('button',{name:'Send message'}));
 await screen.findByText('Your fictional plan has been downgraded.');
 expect(screen.getByRole('button',{name:'Stop simulation'})).toBeTruthy();
})

it('replays a saved example turn by turn and then shows its risk',async()=>{
 const analysis={prediction:{turns:[{turn_index:1,tactics:['flattery'],primary_tactic:'flattery',pressure:2,evidence:[{start:0,end:5,text:'Smart',tactic:'flattery'}],explanation:'Praise.',refusal_before:false,refusal_turn_index:null}],refusals:[],conversation_tactics:['flattery'],escalating:true,explanation:'x'},computed:{timeline:[{turn_index:1,pressure:2,risk:0.42,refusal_before:false}],risk_score:42,peak_risk:0.42,final_risk:0.42,escalating:true,max_pressure:2,refusal_pressure_onset:null,explanation:''},metadata:{model:'m',detected_at:'2026-10-29T10:00:00Z',request_id:'r',prompt_version:'p',attempts:1,latency_ms:10}}
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.endsWith('/recordings')?[{id:'rec',title:'Saved demo',turns:[{speaker:'user',text:'Hi'},{speaker:'assistant',text:'Smart choice to stay.'}],analysis,provenance:{captured_at:'2026-10-29T10:00:00Z',source:'test',note:'n'}}]:{connected:true,model_available:true,model:'m',loaded_models:[],message:''}})))
 const user=userEvent.setup();render(<LiveSimulator initialMode="recorded" geminiConfigured={true} renderAnalysis={()=>null}/>);
 await waitFor(()=>expect(screen.getByRole('option',{name:'Saved demo'})).toBeTruthy());
 await user.selectOptions(screen.getByLabelText('Saved example'),'rec');
 expect(screen.queryByText('choice to stay.')).toBeNull();
 expect(await screen.findByText('choice to stay.',{},{timeout:4000})).toBeTruthy();
 await waitFor(()=>expect(screen.getByRole('img',{name:'Peak risk 42 out of 100'})).toBeTruthy());
 expect(screen.getByText('Smart').getAttribute('data-label')).toBe('Flattery');
})
