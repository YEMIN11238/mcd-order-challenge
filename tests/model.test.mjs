import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fresh, restore, answer, advance, score, shareText } from '../web/model.mjs';

const deck = JSON.parse(readFileSync(new URL('../web/quiz.json', import.meta.url), 'utf8'));

test('all-correct and all-wrong runs produce genuine 5/5 and 0/5 results',()=>{
  for(const chooseRight of [true,false]){
    let state=fresh(deck);
    for(const q of deck.questions){const option=q.options.find(o=>chooseRight?o.id===q.correctId:o.id!==q.correctId);state=advance(deck,answer(deck,state,option.id));}
    assert.equal(state.complete,true);assert.equal(score(deck,state),chooseRight?5:0);
  }
});

test('cannot skip unanswered questions or change an already committed answer',()=>{
  const state=fresh(deck);assert.throws(()=>advance(deck,state));assert.throws(()=>answer(deck,state,'not-an-option'));
  const committed=answer(deck,state,deck.questions[0].correctId);assert.throws(()=>answer(deck,committed,deck.questions[0].options[0].id));
  assert.equal(score(deck,committed),1);assert.deepEqual(state,fresh(deck));
});

test('persisted progress resumes before or after the reveal without losing a committed answer',()=>{
  let state=answer(deck,fresh(deck),deck.questions[0].correctId);assert.deepEqual(restore(deck,JSON.parse(JSON.stringify(state))),state);
  state=advance(deck,state);assert.deepEqual(restore(deck,JSON.parse(JSON.stringify(state))),state);
});

test('old decks, gaps, invalid answer IDs and forged completion flags reset safely',()=>{
  const invalid=[null,{}, {...fresh(deck),deckId:'old'}, {...fresh(deck),current:2}, {...fresh(deck),current:-1}, {...fresh(deck),answers:[]}, {...fresh(deck),answers:{budget:'missing'}}, {...fresh(deck),answers:{promo:'quote'}}, {...fresh(deck),complete:true}];
  for(const value of invalid)assert.deepEqual(restore(deck,value),fresh(deck));
});

test('every possible combination is counted from the answer key, with no random score',()=>{
  let paths=0;
  function visit(state,expected){
    const q=deck.questions[state.current];
    for(const option of q.options){const next=advance(deck,answer(deck,state,option.id));const total=expected+Number(option.id===q.correctId);if(next.complete){assert.equal(score(deck,next),total);assert.ok(total>=0&&total<=5);paths++;}else visit(next,total);}
  }
  visit(fresh(deck),0);assert.equal(paths,108);
});

test('share messages preserve deck identity and historical context, without leaking answer choices',()=>{
  assert.throws(()=>shareText(deck,fresh(deck)));
  let state=fresh(deck);for(const q of deck.questions)state=advance(deck,answer(deck,state,q.correctId));
  const text=shareText(deck,state);
  for(const item of ['5/5','2026-10-20','2026-10-23','非实时','不下单',deck.deckId])assert.ok(text.includes(item));
  assert.ok(!text.includes('correctId'));assert.ok(!text.includes('answers='));
});
