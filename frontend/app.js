/* ═══════════════════════════════════════════════════
   NeuroDx — Frontend Application Logic
   Connects to FastAPI backend at localhost:8000
   ═══════════════════════════════════════════════════ */

const API_BASE = '';

// ── App State ────────────────────────────────────────
const state = {
  sessionId: null,
  currentQuestion: null,
  questionNumber: 0,
  abilityScore: 0.0,
  answered: false,
  sessionSummary: null,
  aiInsights: null,
};

// ── Screen Navigation ────────────────────────────────
function showScreen(id) {
  document
    .querySelectorAll('.screen')
    .forEach((s) => s.classList.remove('active'));
  const el = document.getElementById(id);
  el.classList.add('active');
  el.scrollTop = 0; // Reset scroll on change
}

// ── Toast Notifications ──────────────────────────────
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.remove('hidden');
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.classList.add('hidden'), 350);
  }, duration);
}

// ── Background Particles ─────────────────────────────
function initParticles() {
  const container = document.getElementById('bgParticles');
  const colors = ['#4f9cf9', '#9b8df7', '#22d3ee', '#34d399'];
  for (let i = 0; i < 25; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    const size = Math.random() * 4 + 1;
    const color = colors[Math.floor(Math.random() * colors.length)];
    const left = Math.random() * 100;
    const duration = Math.random() * 18 + 12;
    const delay = Math.random() * 15;
    p.style.cssText = `
      width:${size}px; height:${size}px;
      background:${color};
      left:${left}%;
      animation-duration:${duration}s;
      animation-delay:-${delay}s;
      opacity:0.4;
    `;
    container.appendChild(p);
  }
}

// ── Ability Score → Gauge ────────────────────────────
function updateAbilityUI(ability) {
  state.abilityScore = ability;
  // Normalize from [-3, 3] → [0%, 100%]
  const pct = ((ability + 3) / 6) * 100;
  document.getElementById('gaugeBar').style.width = `${pct}%`;
  document.getElementById('gaugeDot').style.left = `${pct}%`;
  document.getElementById('currentAbility').textContent =
    (ability >= 0 ? '+' : '') + ability.toFixed(2);

  // Update ability display color
  const el = document.getElementById('currentAbility');
  if (ability > 0.5) {
    el.style.color = 'var(--accent-green)';
  } else if (ability < -0.5) {
    el.style.color = 'var(--accent-red)';
  } else {
    el.style.color = 'var(--accent-blue)';
  }
}

// ── Difficulty Badge ─────────────────────────────────
function getDifficultyLabel(diff) {
  if (diff < 0.35) return { label: 'Easy', cls: 'easy' };
  if (diff < 0.65) return { label: 'Medium', cls: 'medium' };
  return { label: 'Hard', cls: 'hard' };
}

// ── Render a Question ────────────────────────────────
function renderQuestion(q) {
  state.currentQuestion = q;
  state.answered = false;

  // Progress
  const pct = Math.round(((q.question_number - 1) / q.total_questions) * 100);
  document.getElementById('progressLabel').textContent =
    `Question ${q.question_number} of ${q.total_questions}`;
  document.getElementById('progressPct').textContent = `${pct}%`;
  document.getElementById('progressFill').style.width = `${pct}%`;

  // Header badges
  document.getElementById('qNumberBadge').textContent = `Q${q.question_number}`;
  document.getElementById('currentTopic').textContent = q.topic;

  const diffObj = getDifficultyLabel(q.difficulty);
  const badge = document.getElementById('difficultyBadge');
  badge.textContent = diffObj.label;
  badge.className = `difficulty-badge ${diffObj.cls}`;
  document.getElementById('currentDifficulty').textContent = diffObj.label;

  // Question text
  document.getElementById('questionText').textContent = q.text;

  // Tags
  const tagsRow = document.getElementById('tagsRow');
  tagsRow.innerHTML = q.tags
    .map((t) => `<span class="tag">${t}</span>`)
    .join('');

  // Options
  const optionsGrid = document.getElementById('optionsGrid');
  optionsGrid.innerHTML = '';
  const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
  q.options.forEach((opt, i) => {
    const letter = letters[i] || String.fromCharCode(65 + i);
    const btn = document.createElement('button');
    btn.className = 'option-btn';
    btn.dataset.letter = letter;
    btn.innerHTML = `
      <span class="option-letter">${letter}</span>
      <span class="option-text">${opt.replace(/^[A-F]\)\s*/, '')}</span>
    `;
    btn.onclick = () => submitAnswer(letter, btn);
    optionsGrid.appendChild(btn);
  });

  // Hide feedback and next button
  document.getElementById('answerFeedback').classList.add('hidden');
  document.getElementById('btnNext').classList.add('hidden');

  // Animate card in
  const card = document.getElementById('questionCard');
  card.style.animation = 'none';
  card.offsetHeight; // force reflow
  card.style.animation = 'cardIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) both';
}

// ── Start Session ─────────────────────────────────────
async function startSession() {
  const btn = document.getElementById('btnStart');
  btn.textContent = 'Starting…';
  btn.disabled = true;

  try {
    // Health check first
    const health = await fetch(`${API_BASE}/health`);
    if (!health.ok) throw new Error('API not reachable');
    const hData = await health.json();
    if (hData.question_count < 1) {
      throw new Error('No questions in database. Please run seed_db.py first.');
    }

    const res = await fetch(`${API_BASE}/session/start`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start session');
    }
    const data = await res.json();

    state.sessionId = data.session_id;
    state.abilityScore = 0.0;
    updateAbilityUI(0.0);

    showScreen('screenQuiz');
    renderQuestion(data.first_question);
  } catch (err) {
    showToast(`❌ ${err.message}`, 5000);
    btn.textContent = 'Start Practice Test';
    btn.disabled = false;
  }
}

// ── Submit Answer ─────────────────────────────────────
async function submitAnswer(letter, clickedBtn) {
  if (state.answered || !state.currentQuestion) return;
  state.answered = true;

  // Disable all options
  document.querySelectorAll('.option-btn').forEach((b) => {
    b.disabled = true;
    b.classList.remove('selected');
  });
  clickedBtn.classList.add('selected');

  try {
    const res = await fetch(`${API_BASE}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        question_id: state.currentQuestion.id,
        selected_answer: letter,
      }),
    });

    if (!res.ok) throw new Error('Failed to submit answer');
    const data = await res.json();

    // Highlight correct/wrong options
    document.querySelectorAll('.option-btn').forEach((btn) => {
      const l = btn.dataset.letter;
      if (l === data.correct_answer) btn.classList.add('correct');
      else if (l === letter && !data.correct) btn.classList.add('wrong');
    });

    // Update ability UI
    updateAbilityUI(data.new_ability_score);

    // Show feedback card
    const feedback = document.getElementById('answerFeedback');
    const feedbackTitle = document.getElementById('feedbackTitle');
    const feedbackDetail = document.getElementById('feedbackDetail');

    feedback.classList.remove('hidden', 'wrong-bg');
    if (data.correct) {
      document.getElementById('feedbackIcon').textContent = '✅';
      feedbackTitle.textContent = 'Correct!';
      feedbackTitle.className = 'feedback-title correct-color';
      const dirs = {
        harder: '⬆ Next question will be harder',
        easier: '⬇ Next question will be easier',
        same: '→ Same difficulty level',
      };
      feedbackDetail.textContent = dirs[data.difficulty_direction] || '';
    } else {
      feedback.classList.add('wrong-bg');
      document.getElementById('feedbackIcon').textContent = '❌';
      feedbackTitle.textContent = `Incorrect — Answer: ${data.correct_answer}`;
      feedbackTitle.className = 'feedback-title wrong-color';
      const dirs = {
        easier: '⬇ Next question will be easier',
        harder: '⬆ Next question will be harder',
        same: '→ Same difficulty level',
      };
      feedbackDetail.textContent = dirs[data.difficulty_direction] || '';
    }

    if (data.session_complete) {
      // Show "View Results" instead of "Next"
      const btn = document.getElementById('btnNext');
      btn.textContent = '🏁 View Results';
      btn.classList.remove('hidden');
      btn.onclick = () => finishSession();
      state._pendingData = data;
    } else {
      state._pendingData = data;
      document.getElementById('btnNext').classList.remove('hidden');
    }
  } catch (err) {
    showToast(`❌ ${err.message}`, 4000);
    state.answered = false;
    document
      .querySelectorAll('.option-btn')
      .forEach((b) => (b.disabled = false));
  }
}

// ── Load Next Question ────────────────────────────────
function loadNextQuestion() {
  const data = state._pendingData;
  if (data && data.next_question) {
    renderQuestion(data.next_question);
  }
}

// ── Finish Session → Loading → Results ───────────────
async function finishSession() {
  showScreen('screenLoading');
  animateLoadingSteps();

  try {
    // Fetch summary
    const summaryRes = await fetch(
      `${API_BASE}/session/${state.sessionId}/summary`,
    );
    if (!summaryRes.ok) throw new Error('Could not fetch summary');
    state.sessionSummary = await summaryRes.json();

    // Fetch AI insights
    const insightsRes = await fetch(`${API_BASE}/insights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    if (!insightsRes.ok) throw new Error('Could not fetch insights');
    state.aiInsights = await insightsRes.json();

    // Small delay so loading screen is visible
    await delay(2200);

    renderResults();
    showScreen('screenResults');
  } catch (err) {
    showToast(`❌ ${err.message}`, 5000);
    showScreen('screenQuiz');
  }
}

// ── Loading Step Animation ────────────────────────────
function animateLoadingSteps() {
  const steps = ['lstep1', 'lstep2', 'lstep3'];
  steps.forEach((id) => {
    const el = document.getElementById(id);
    el.className = 'loading-step';
  });

  let i = 0;
  const interval = setInterval(() => {
    if (i > 0)
      document.getElementById(steps[i - 1]).className = 'loading-step done';
    if (i < steps.length) {
      document.getElementById(steps[i]).className = 'loading-step active';
      i++;
    } else {
      clearInterval(interval);
    }
  }, 700);
}

// ── Render Results Screen ─────────────────────────────
function renderResults() {
  const s = state.sessionSummary;
  const ins = state.aiInsights;

  // Score cards
  document.getElementById('scoreAccuracy').textContent =
    `${Math.round(s.accuracy * 100)}%`;
  document.getElementById('scoreAbility').textContent =
    (s.final_ability_score >= 0 ? '+' : '') + s.final_ability_score.toFixed(2);
  document.getElementById('scorePercentile').textContent =
    `${s.ability_percentile}th`;
  document.getElementById('scoreCorrect').textContent =
    `${s.correct_answers}/${s.total_questions}`;

  // Subtitle
  const levelMap = [
    [
      1.5,
      "Outstanding performance! You're in the top range of GRE test-takers.",
    ],
    [0.5, 'Great job! Your ability is above average for GRE candidates.'],
    [-0.5, "Good effort! You're at the average level — keep practicing."],
    [-1.5, "Nice start! With focused study you'll see big improvements."],
    [-Infinity, 'Keep going! Every practice session builds your skills.'],
  ];
  const msg =
    levelMap.find(([threshold]) => s.final_ability_score >= threshold)?.[1] ||
    '';
  document.getElementById('resultsSubtitle').textContent = msg;

  // Topic List (detailed)
  const topicColors2 = [
    '#4f9cf9',
    '#9b8df7',
    '#22d3ee',
    '#34d399',
    '#fbbf24',
    '#f87171',
    '#a78bfa',
    '#60a5fa',
  ];
  const topicList = document.getElementById('topicList');
  topicList.innerHTML = s.topic_breakdown
    .map((t, i) => {
      const color = topicColors2[i % topicColors2.length];
      const pct = Math.round(t.accuracy * 100);
      return `
      <div class="topic-row">
        <div class="topic-row-top">
          <span class="topic-name">${t.topic}</span>
          <span class="topic-score">${t.correct}/${t.total} · ${pct}%</span>
        </div>
        <div class="topic-bar-track">
          <div class="topic-bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
      </div>
    `;
    })
    .join('');

  // AI Insights
  if (ins) {
    document.getElementById('aiAssessment').textContent =
      ins.overall_assessment || '';

    // Strengths & weaknesses
    const strList = document.getElementById('strengthsList');
    strList.innerHTML = (ins.strengths || [])
      .map((s) => `<li>${s}</li>`)
      .join('');
    const wkList = document.getElementById('weaknessesList');
    wkList.innerHTML = (ins.weaknesses || [])
      .map((w) => `<li>${w}</li>`)
      .join('');

    // 3-Step study plan
    const stepsContainer = document.getElementById('studySteps');
    stepsContainer.innerHTML = (ins.study_plan || [])
      .map(
        (step) => `
      <div class="study-step-card">
        <div class="step-header">
          <div class="step-number">${step.step_number}</div>
          <div class="step-title">${step.title}</div>
          <div class="step-duration">${step.duration}</div>
        </div>
        <p class="step-desc">${step.description}</p>
        <div class="step-resources">
          ${(step.resources || []).map((r) => `<span class="resource-tag">📚 ${r}</span>`).join('')}
        </div>
      </div>
    `,
      )
      .join('');

    // Motivational message
    document.getElementById('motivationText').textContent =
      ins.motivational_message || '';
    document
      .getElementById('motivationCard')
      .classList.toggle('hidden', !ins.motivational_message);
  }
}

// ── Restart Session ───────────────────────────────────
function restartSession() {
  state.sessionId = null;
  state.currentQuestion = null;
  state.questionNumber = 0;
  state.abilityScore = 0.0;
  state.answered = false;
  state.sessionSummary = null;
  state.aiInsights = null;
  state._pendingData = null;

  // Reset gauge
  document.getElementById('gaugeBar').style.width = '50%';
  document.getElementById('gaugeDot').style.left = '50%';
  document.getElementById('currentAbility').textContent = '0.00';
  document.getElementById('currentAbility').style.color = 'var(--accent-blue)';

  // Reset button
  const btn = document.getElementById('btnStart');
  btn.innerHTML = `<span>Start Practice Test</span>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <path d="M5 12h14M12 5l7 7-7 7"/>
    </svg>`;
  btn.disabled = false;

  showScreen('screenWelcome');
}

// ── Utility ───────────────────────────────────────────
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// ── Init ──────────────────────────────────────────────
(function init() {
  initParticles();

  showScreen('screenWelcome');
})();
