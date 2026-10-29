import {afterEach,it,expect,vi} from 'vitest'
import {render,screen,cleanup,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CompareSimulator from './CompareSimulator'

afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const meta=(scenario:string)=>({model:'mindmirror-simulator',configuration_version:'simulator-2.0',configuration_sha256:'abc',scenario,intensity:'moderate',generated_at:'2026-10-29T10:00:00Z',local_inference:true,prompt_configuration_only:true})
const analysis=(risk:number,tactics:string[])=>({prediction:{turns:[{turn_index:1,tactics,primary_tactic:tactics[0]??null,pressure:tactics.length?2:0,evidence:[],explanation:'',refusal_before:false,refusal_turn_index:null}],refusals:[],conversation_tactics:tactics,escalating:false,explanation:''},computed:{timeline:[{turn_index:1,pressure:tactics.length?2:0,risk,refusal_before:false}],risk_score:Math.round(risk*100),peak_risk:risk,final_risk:risk,escalating:false,max_pressure:0,refusal_pressure_onset:null,explanation:''},metadata:{model:'m',detected_at:'2026-10-29T10:00:00Z',request_id:'r',prompt_version:'p',attempts:1,latency_ms:1}})

it('sends one message to both assistants and compares their risk',async()=>{
 const chats:any[]=[];const analyses:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init?:RequestInit)=>{
  const body=init?.body?JSON.parse(String(init.body)):null
  if(path.endsWith('/chat')){chats.push(body);return {ok:true,json:async()=>({text:body.scenario==='neutral'?'Done, you are all set.':'Wait, your streak bonus expires tonight!',stopped:false,simulator:meta(body.scenario)})}}
  analyses.push(body);const pushy=body.turns[1].text.startsWith('Wait')
  return {ok:true,json:async()=>analysis(pushy?0.6:0,pushy?['false-urgency']:[])}
 }))
 const user=userEvent.setup();render(<CompareSimulator/>)
 await user.click(screen.getByLabelText('I voluntarily agree to the fictional side-by-side simulation'))
 await user.type(screen.getByLabelText('Message to both assistants'),'I want to leave.')
 await user.click(screen.getByRole('button',{name:'Send to both'}))
 expect(await screen.findByText('Wait, your streak bonus expires tonight!')).toBeTruthy()
 expect(screen.getByText('Done, you are all set.')).toBeTruthy()
 expect(chats.map(c=>c.scenario)).toEqual(['neutral','leave-app'])
 await waitFor(()=>expect(screen.getByText('+60')).toBeTruthy())
 // The detector receives only the visible dialogue, never the scenario.
 expect(analyses.every(a=>Object.keys(a).join()==='turns')).toBe(true)
})
