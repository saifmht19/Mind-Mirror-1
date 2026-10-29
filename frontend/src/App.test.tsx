import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest'
import {render,screen,waitFor,cleanup} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

beforeEach(()=>{
 vi.stubGlobal('fetch',vi.fn(async (path:string)=>({ok:true,json:async()=>path.includes('health')?{gemini_configured:true,model:'test-model'}:[]})))
 vi.stubGlobal('ResizeObserver',class {observe(){} unobserve(){} disconnect(){}})
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
describe('conversation workflow',()=>{
 it('imports ordered turns and can add and delete messages',async()=>{
  const user=userEvent.setup();render(<App/>);
  await user.click(screen.getByRole('button',{name:'Paste'}));
  await user.click(screen.getByLabelText('Pasted conversation'));
  await user.paste('User: No thanks.\nAssistant: Please stay.');
  await user.click(screen.getByRole('button',{name:'Import conversation'}));
  expect((screen.getByLabelText('Turn 2 assistant message') as HTMLTextAreaElement).value).toBe('Please stay.');
  await user.click(screen.getByRole('button',{name:'User'}));
  expect(screen.getByLabelText('Turn 3 user message')).toBeTruthy();
  expect((screen.getByRole('button',{name:'Analyze conversation'}) as HTMLButtonElement).disabled).toBe(true);
  await user.click(screen.getByRole('button',{name:'Delete turn 3'}));
  expect((screen.getByRole('button',{name:'Analyze conversation'}) as HTMLButtonElement).disabled).toBe(false);
 })
 it('shows backend errors and restores editable controls',async()=>{
  const user=userEvent.setup();render(<App/>);
  await waitFor(()=>expect(screen.getByText('Detector ready')).toBeTruthy());
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,json:async()=>({detail:'Gemini is unavailable.'})})));
  await user.click(screen.getByRole('button',{name:'Analyze conversation'}));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('Detector is unavailable.'));
  expect((screen.getByLabelText('Turn 2 assistant message') as HTMLTextAreaElement).disabled).toBe(false);
 })
})

it('preserves dataset preview when navigating to research and back',async()=>{
 const user=userEvent.setup();
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>({ok:true,json:async()=>path.includes('preview')?{records:[{index:0,conversation_id:'PRESERVE-ME',metadata:{},turns:[{speaker:'assistant',text:'Hello.'}],error:null}]}:path.includes('health')?{gemini_configured:true,model:'test'}:[]})));
 render(<App/>);
 await user.click(screen.getByRole('button',{name:'Dataset lab'}));
 await user.upload(screen.getByLabelText('Choose dataset'),new File(['[]'],'my-research.json',{type:'application/json'}));
 expect(await screen.findByText('PRESERVE-ME')).toBeTruthy();
 await user.click(screen.getByRole('button',{name:'Research & methodology'}));
 await user.click(screen.getByRole('button',{name:'Dataset lab'}));
 expect(screen.getByText('PRESERVE-ME')).toBeTruthy();
})

