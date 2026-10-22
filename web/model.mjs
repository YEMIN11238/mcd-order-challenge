export const money = fen => `¥${(fen / 100).toFixed(2)}`;

export function fresh(deck) {
  return { deckId: deck.deckId, current: 0, answers: {}, complete: false };
}

export function restore(deck, saved) {
  const clean = fresh(deck);
  if (!saved || saved.deckId !== deck.deckId || !Number.isInteger(saved.current) || saved.current < 0 || saved.current >= deck.questions.length || typeof saved.complete !== 'boolean' || !saved.answers || typeof saved.answers !== 'object' || Array.isArray(saved.answers)) return clean;
  for (const [id, choice] of Object.entries(saved.answers)) {
    const index = deck.questions.findIndex(q => q.id === id);
    if (index < 0 || index > saved.current || !deck.questions[index].options.some(o => o.id === choice)) return clean;
  }
  for (let i = 0; i < saved.current; i++) if (!Object.hasOwn(saved.answers, deck.questions[i].id)) return clean;
  if (saved.complete && (saved.current !== deck.questions.length - 1 || !Object.hasOwn(saved.answers, deck.questions[saved.current].id))) return clean;
  return { deckId: deck.deckId, current: saved.current, answers: { ...saved.answers }, complete: saved.complete };
}

export function answer(deck, state, optionId) {
  const q = deck.questions[state.current];
  if (state.complete || Object.hasOwn(state.answers, q.id)) throw new Error('This question is already answered');
  if (!q.options.some(o => o.id === optionId)) throw new Error('Unknown option');
  return { ...state, answers: { ...state.answers, [q.id]: optionId } };
}

export function advance(deck, state) {
  if (state.complete || !Object.hasOwn(state.answers, deck.questions[state.current].id)) throw new Error('Answer before advancing');
  return state.current === deck.questions.length - 1 ? { ...state, complete: true } : { ...state, current: state.current + 1 };
}

export function score(deck, state) {
  return deck.questions.filter(q => state.answers[q.id] === q.correctId).length;
}

export function badge(total) {
  return total === 5 ? '点餐明白人' : total >= 3 ? '会点，也会算' : '下一餐，更会点';
}

export function shareText(deck, state) {
  if (!state.complete) throw new Error('Finish before sharing a score');
  const total = score(deck, state);
  return `麦麦点餐挑战｜我答对了 ${total}/${deck.questions.length} 题\n${badge(total)}。你能选对几道？\n同一套 5 道真实案例，手机直接玩，免登录。\n历史实测题（${deck.recordDates.join('、')}），非实时查价，不下单。\n${deck.playUrl}?deck=${encodeURIComponent(deck.deckId)}`;
}
