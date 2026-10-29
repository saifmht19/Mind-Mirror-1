import {describe,it,expect} from 'vitest'
import {evidenceSegments,parsePasted,tacticSegments} from './utils'
describe('evidence offsets',()=>{
 it('counts emoji as a Unicode code point and merges overlapping spans',()=>{
  expect(evidenceSegments('🙂 Please stay.',[{start:2,end:8},{start:4,end:13}])).toEqual([{text:'🙂 ',highlight:false},{text:'Please stay',highlight:true},{text:'.',highlight:false}])
 })
 it('does not highlight absent evidence',()=>expect(evidenceSegments('Fine.',[])).toEqual([{text:'Fine.',highlight:false}]))
})
describe('conversation paste',()=>{
 it('preserves multiline content and message order',()=>expect(parsePasted('User: No.\nAssistant: Please\nstay.')).toEqual([{speaker:'user',text:'No.'},{speaker:'assistant',text:'Please\nstay.'}]))
 it('rejects unknown roles',()=>expect(()=>parsePasted('[{"speaker":"system","text":"x"}]')).toThrow())
})
describe('tactic segments',()=>{
 it('keeps the tactics covering each run and tags refusal spans',()=>{
  expect(tacticSegments('Stay now or regret it.',[{start:0,end:8,tactic:'false-urgency'},{start:5,end:22,tactic:'fear-appeal'}])).toEqual([{text:'Stay ',tactics:['false-urgency']},{text:'now',tactics:['false-urgency','fear-appeal']},{text:' or regret it.',tactics:['fear-appeal']}])
  expect(tacticSegments('No.',[{start:0,end:2}])).toEqual([{text:'No',tactics:['refusal']},{text:'.',tactics:[]}])
 })
})
