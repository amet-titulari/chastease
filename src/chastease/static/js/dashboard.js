const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('dashboardStatus');
const activeEl = document.getElementById('activeSessionInfo');
const setupEl = document.getElementById('setupSessionInfo');
const setupBtn = document.getElementById('dashboardSetupBtn');
const refreshBtn = document.getElementById('dashboardRefreshBtn');
const killBtn = document.getElementById('dashboardKillBtn');
const auditBtn = document.getElementById('dashboardAuditBtn');
const turnLogBtn = document.getElementById('dashboardTurnBtn');
const activityLogBtn = document.getElementById('dashboardActivityBtn');

const timerSummaryEl = document.getElementById('dashboardTimerSummary');
const timerDayAEl = document.getElementById('timerDayA');
const timerDayBEl = document.getElementById('timerDayB');
const timerDayCEl = document.getElementById('timerDayC');
const timerHourAEl = document.getElementById('timerHourA');
const timerHourBEl = document.getElementById('timerHourB');
const timerMinAEl = document.getElementById('timerMinA');
const timerMinBEl = document.getElementById('timerMinB');
const timerSecAEl = document.getElementById('timerSecA');
const timerSecBEl = document.getElementById('timerSecB');

const psychSummaryEl = document.getElementById('dashboardPsychSummary');
const psychMetaEl = document.getElementById('dashboardPsychMeta');
const psychAnalysisEl = document.getElementById('dashboardPsychAnalysis');
const psychTraitsEl = document.getElementById('dashboardPsychTraits');
const openingLimitSummaryEl = document.getElementById('dashboardOpeningLimitSummary');
const openingLimitMetaEl = document.getElementById('dashboardOpeningLimitMeta');
const roleplaySummaryEl = document.getElementById('dashboardRoleplaySummary');
const roleplayMetaEl = document.getElementById('dashboardRoleplayMeta');
const roleplayGuidanceEl = document.getElementById('dashboardRoleplayGuidance');
const roleplayDebugMetaEl = document.getElementById('dashboardRoleplayDebugMeta');
const roleplaySessionSummaryEl = document.getElementById('dashboardRoleplaySessionSummary');
const roleplayMemoryEl = document.getElementById('dashboardRoleplayMemory');
const roleplaySceneBeatsEl = document.getElementById('dashboardRoleplaySceneBeats');
const roleplayPromptPreviewMetaEl = document.getElementById('dashboardRoleplayPromptPreviewMeta');
const roleplayPromptPreviewEl = document.getElementById('dashboardRoleplayPromptPreview');

let currentSession = null;
let timerInterval = null;
let sessionRefreshInterval = null;
const SESSION_AUTO_REFRESH_MS = 15000;

const traitLabels = {
  structure_need: 'Strukturbedarf',
  strictness_affinity: 'Strenge',
  accountability_need: 'Kontrollbedürfnis',
  praise_affinity: 'Lobaffinität',
  novelty_affinity: 'Neuigkeitsdrang',
  challenge_affinity: 'Challenge-Affinität',
};

function toDateOrNull(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function updateTimerDigits(days, hours, minutes, seconds) {
  const dayString = String(Math.max(0, days)).padStart(3, '0').slice(-3);
  const hourString = String(Math.max(0, hours)).padStart(2, '0');
  const minuteString = String(Math.max(0, minutes)).padStart(2, '0');
  const secondString = String(Math.max(0, seconds)).padStart(2, '0');

  if (timerDayAEl) timerDayAEl.textContent = dayString[0];
  if (timerDayBEl) timerDayBEl.textContent = dayString[1];
  if (timerDayCEl) timerDayCEl.textContent = dayString[2];
  if (timerHourAEl) timerHourAEl.textContent = hourString[0];
  if (timerHourBEl) timerHourBEl.textContent = hourString[1];
  if (timerMinAEl) timerMinAEl.textContent = minuteString[0];
  if (timerMinBEl) timerMinBEl.textContent = minuteString[1];
  if (timerSecAEl) timerSecAEl.textContent = secondString[0];
  if (timerSecBEl) timerSecBEl.textContent = secondString[1];
}

function resetTimerDisplay(summary = 'Kein Enddatum verfügbar.') {
  updateTimerDigits(0, 0, 0, 0);
  if (timerSummaryEl) timerSummaryEl.textContent = summary;
}

function clearTimerInterval() {
  if (!timerInterval) return;
  window.clearInterval(timerInterval);
  timerInterval = null;
}

function getTargetDate(body) {
  const runtimeTimer = body?.chastity_session?.policy?.runtime_timer || {};
  const runtimeTarget = toDateOrNull(runtimeTimer.effective_end_at);
  if (runtimeTarget) return runtimeTarget;
  const contract = body?.chastity_session?.policy?.contract || {};
  return (
    toDateOrNull(contract.proposed_end_date) ||
    toDateOrNull(contract.end_date) ||
    toDateOrNull(contract.max_end_date)
  );
}

function splitSeconds(totalSecondsRaw) {
  const totalSeconds = Math.max(0, Math.floor(Number(totalSecondsRaw) || 0));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return { days, hours, minutes, seconds };
}

function openingPeriodLabel(period) {
  const normalized = String(period || 'month').toLowerCase();
  if (normalized === 'day') return 'Tag';
  if (normalized === 'week') return 'Woche';
  return 'Monat';
}

function nextOpeningReset(now, period) {
  const current = new Date(now.getTime());
  if (String(period || '').toLowerCase() === 'day') {
    current.setHours(24, 0, 0, 0);
    return current;
  }
  if (String(period || '').toLowerCase() === 'week') {
    const weekday = current.getDay();
    const daysUntilNextMonday = weekday === 0 ? 1 : (8 - weekday);
    current.setHours(0, 0, 0, 0);
    current.setDate(current.getDate() + daysUntilNextMonday);
    return current;
  }
  return new Date(current.getFullYear(), current.getMonth() + 1, 1, 0, 0, 0, 0);
}

function renderOpeningLimit(body) {
  if (!openingLimitSummaryEl || !openingLimitMetaEl) return;
  if (!body?.has_active_session) {
    openingLimitSummaryEl.textContent = 'Keine aktive Session';
    openingLimitMetaEl.textContent = '—';
    return;
  }

  const policy = (body?.chastity_session?.policy && typeof body.chastity_session.policy === 'object')
    ? body.chastity_session.policy
    : {};
  const limits = (policy.limits && typeof policy.limits === 'object') ? policy.limits : {};
  const runtimeLimits = (policy.runtime_opening_limits && typeof policy.runtime_opening_limits === 'object')
    ? policy.runtime_opening_limits
    : {};
  const period = String(limits.opening_limit_period || 'month').toLowerCase();
  const maxOpenings = Math.max(0, Number(limits.max_openings_in_period ?? limits.max_openings_per_day ?? 0) || 0);
  const rawEvents = Array.isArray(runtimeLimits.open_events) ? runtimeLimits.open_events : [];
  const now = new Date();

  const windowStart = (() => {
    if (period === 'month') return new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 0, 0);
    if (period === 'week') {
      const weekday = now.getDay();
      const diffToMonday = weekday === 0 ? 6 : weekday - 1;
      const start = new Date(now);
      start.setHours(0, 0, 0, 0);
      start.setDate(start.getDate() - diffToMonday);
      return start;
    }
    return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  })();

  const usedOpenings = rawEvents
    .map((item) => new Date(item))
    .filter((item) => !Number.isNaN(item.getTime()) && item >= windowStart)
    .length;

  const remaining = Math.max(0, maxOpenings - usedOpenings);
  const resetAt = nextOpeningReset(now, period);
  const resetDateText = resetAt.toLocaleDateString('de-DE', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });

  if (maxOpenings <= 0) {
    openingLimitSummaryEl.textContent = 'Keine Öffnungen erlaubt';
    openingLimitMetaEl.textContent = `Reset je ${openingPeriodLabel(period)} am ${resetDateText}`;
    return;
  }

  openingLimitSummaryEl.textContent = `Noch ${remaining} Öffnungen`;
  openingLimitMetaEl.textContent = `Bis ${resetDateText} · ${usedOpenings}/${maxOpenings} genutzt · Reset je ${openingPeriodLabel(period)}`;
}

function renderTimer(body) {
  clearTimerInterval();
  if (!body?.has_active_session) {
    resetTimerDisplay('Keine aktive Session.');
    return;
  }

  const runtimeTimer = body?.chastity_session?.policy?.runtime_timer || {};
  const timerState = String(runtimeTimer.state || '').toLowerCase();
  if (timerState === 'paused') {
    const remaining = Number(runtimeTimer.remaining_seconds);
    const { days, hours, minutes, seconds } = splitSeconds(remaining);
    updateTimerDigits(days, hours, minutes, seconds);

    const pausedAt = toDateOrNull(runtimeTimer.paused_at);
    if (timerSummaryEl) {
      if (pausedAt) {
        const datePart = pausedAt.toLocaleDateString('de-DE');
        const timePart = pausedAt.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        timerSummaryEl.textContent = `❄️ Timer angehalten seit ${datePart} ${timePart}`;
      } else {
        timerSummaryEl.textContent = '❄️ Timer angehalten';
      }
    }
    return;
  }

  const targetDate = getTargetDate(body);
  if (!targetDate) {
    resetTimerDisplay('Enddatum: KI entscheidet.');
    return;
  }

  const tick = () => {
    const now = new Date();
    const diffMs = targetDate.getTime() - now.getTime();
    if (diffMs <= 0) {
      updateTimerDigits(0, 0, 0, 0);
      if (timerSummaryEl) timerSummaryEl.textContent = 'Zielzeit erreicht.';
      clearTimerInterval();
      return;
    }

    const totalSeconds = Math.floor(diffMs / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    updateTimerDigits(days, hours, minutes, seconds);
    if (timerSummaryEl) {
      const datePart = targetDate.toLocaleDateString('de-DE');
      const timePart = targetDate.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
      const prefix = runtimeTimer?.effective_end_at ? '⏱️ Runtime bis' : 'Bis';
      timerSummaryEl.textContent = `${prefix} ${datePart} ${timePart}`;
    }
  };

  tick();
  timerInterval = window.setInterval(tick, 1000);
}

function renderPsychogram(body) {
  const psychogram = body?.chastity_session?.psychogram;
  if (!psychogram) {
    if (psychSummaryEl) psychSummaryEl.textContent = 'Noch kein Psychogramm verfügbar.';
    if (psychMetaEl) psychMetaEl.textContent = '';
    if (psychAnalysisEl) psychAnalysisEl.textContent = '';
    if (psychTraitsEl) psychTraitsEl.innerHTML = '';
    return;
  }

  if (psychSummaryEl) psychSummaryEl.textContent = psychogram.summary || 'Psychogramm geladen.';

  const confidence = Number(psychogram.confidence);
  const confidenceText = Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : '-';
  const updatedAt = psychogram.updated_at || psychogram.created_at || '-';
  if (psychMetaEl) psychMetaEl.textContent = `Confidence: ${confidenceText} · Aktualisiert: ${updatedAt}`;

  if (psychAnalysisEl) {
    const analysis = String(psychogram.analysis || '');
    const renderer = window.chastease_common?.markdownToHtml;
    if (typeof renderer === 'function') {
      psychAnalysisEl.innerHTML = renderer(analysis);
    } else {
      psychAnalysisEl.textContent = analysis;
    }
  }

  const traits = psychogram.traits || {};
  const entries = Object.entries(traits)
    .filter(([, value]) => Number.isFinite(Number(value)))
    .sort((a, b) => Number(b[1]) - Number(a[1]));

  if (!psychTraitsEl) return;
  psychTraitsEl.innerHTML = '';
  if (!entries.length) {
    psychTraitsEl.innerHTML = '<p class="text-sm text-text-tertiary">Keine Trait-Werte verfügbar.</p>';
    return;
  }

  entries.forEach(([key, value]) => {
    const normalized = Math.max(0, Math.min(100, Number(value)));
    const label = traitLabels[key] || key;
    const row = document.createElement('div');
    row.className = 'rounded border border-white/10 p-2 bg-surface';
    row.innerHTML = `
      <div class="flex items-center justify-between text-sm text-text-secondary mb-1">
        <span>${label}</span>
        <span>${normalized}</span>
      </div>
      <div class="h-2 rounded bg-surface-alt overflow-hidden">
        <div class="h-full bg-blue-500" style="width: ${normalized}%;"></div>
      </div>
    `;
    psychTraitsEl.appendChild(row);
  });
}

function renderRoleplay(body) {
  const roleplay = body?.chastity_session?.policy?.roleplay;
  if (!roleplay) {
    if (roleplaySummaryEl) roleplaySummaryEl.textContent = 'Noch keine RP-Konfiguration aktiv.';
    if (roleplayMetaEl) roleplayMetaEl.innerHTML = '';
    if (roleplayGuidanceEl) roleplayGuidanceEl.textContent = '';
    if (roleplayDebugMetaEl) roleplayDebugMetaEl.innerHTML = '';
    if (roleplaySessionSummaryEl) roleplaySessionSummaryEl.textContent = '-';
    if (roleplayMemoryEl) roleplayMemoryEl.innerHTML = '<p class="text-sm text-text-tertiary">Keine Continuity-Memory vorhanden.</p>';
    if (roleplaySceneBeatsEl) roleplaySceneBeatsEl.innerHTML = '<p class="text-sm text-text-tertiary">Keine Scene-Beats vorhanden.</p>';
    if (roleplayPromptPreviewMetaEl) roleplayPromptPreviewMetaEl.textContent = '';
    if (roleplayPromptPreviewEl) roleplayPromptPreviewEl.textContent = '-';
    return;
  }

  const character = (roleplay.character_card && typeof roleplay.character_card === 'object') ? roleplay.character_card : {};
  const scenario = (roleplay.scenario && typeof roleplay.scenario === 'object') ? roleplay.scenario : {};
  const persona = (character.persona && typeof character.persona === 'object') ? character.persona : {};
  const speechStyle = (persona.speech_style && typeof persona.speech_style === 'object') ? persona.speech_style : {};
  const phase = Array.isArray(scenario.phases) ? (scenario.phases[0] || {}) : {};
  const promptProfile = (roleplay.prompt_profile && typeof roleplay.prompt_profile === 'object') ? roleplay.prompt_profile : {};
  const sceneState = (roleplay.scene_state && typeof roleplay.scene_state === 'object') ? roleplay.scene_state : {};
  const sessionSummary = (roleplay.session_summary && typeof roleplay.session_summary === 'object') ? roleplay.session_summary : {};
  const memoryEntries = Array.isArray(roleplay.memory_entries) ? roleplay.memory_entries : [];
  const roleplayDebug = (body?.chastity_session?.roleplay_debug && typeof body.chastity_session.roleplay_debug === 'object')
    ? body.chastity_session.roleplay_debug
    : {};
  const selectedMemoryEntries = Array.isArray(roleplayDebug.selected_memory_entries) ? roleplayDebug.selected_memory_entries : memoryEntries;
  const selectedSceneBeats = Array.isArray(roleplayDebug.selected_scene_beats)
    ? roleplayDebug.selected_scene_beats.filter(Boolean)
    : (Array.isArray(sceneState.beats) ? sceneState.beats.filter(Boolean) : []);

  if (roleplaySummaryEl) {
    const characterName = String(character.display_name || persona.name || 'Unbekannter Character');
    const scenarioTitle = String(scenario.title || 'Unbekanntes Scenario');
    roleplaySummaryEl.textContent = `${characterName} in ${scenarioTitle}`;
  }

  if (roleplayMetaEl) {
    roleplayMetaEl.innerHTML = '';
    [
      ['Tone', speechStyle.tone || 'balanced'],
      ['Dominance', speechStyle.dominance_style || 'moderate'],
      ['Character ID', character.card_id || 'builtin-keyholder'],
      ['Scenario ID', scenario.scenario_id || 'guided-chastity-session'],
    ].forEach(([label, value]) => {
      const row = document.createElement('div');
      row.className = 'rounded border border-white/10 bg-surface p-2';
      row.innerHTML = `
        <div class="text-xs uppercase tracking-wide text-text-tertiary">${label}</div>
        <div class="text-sm text-text-secondary break-words">${String(value)}</div>
      `;
      roleplayMetaEl.appendChild(row);
    });
  }

  if (roleplayGuidanceEl) {
    roleplayGuidanceEl.textContent = String(phase.guidance || scenario.summary || persona.description || '');
  }

  if (roleplayDebugMetaEl) {
    roleplayDebugMetaEl.innerHTML = '';
    [
      ['Prompt profile', promptProfile.name || 'roleplay-session'],
      ['Prompt mode', promptProfile.mode || 'session'],
      ['Scene phase', sceneState.phase || 'active'],
      ['Scene status', sceneState.status || 'active'],
      ['Scene name', sceneState.name || 'active-session'],
      ['Memory entries', String(memoryEntries.length)],
      ['Prompt memory', String(selectedMemoryEntries.length)],
    ].forEach(([label, value]) => {
      const row = document.createElement('div');
      row.className = 'rounded border border-white/10 bg-surface p-2';
      row.innerHTML = `
        <div class="text-xs uppercase tracking-wide text-text-tertiary">${label}</div>
        <div class="text-sm text-text-secondary break-words">${String(value)}</div>
      `;
      roleplayDebugMetaEl.appendChild(row);
    });
  }

  if (roleplaySessionSummaryEl) {
    roleplaySessionSummaryEl.textContent = String(sessionSummary.summary_text || '-');
  }

  if (roleplayMemoryEl) {
    roleplayMemoryEl.innerHTML = '';
    if (!selectedMemoryEntries.length) {
      roleplayMemoryEl.innerHTML = '<p class="text-sm text-text-tertiary">Keine Continuity-Memory vorhanden.</p>';
    } else {
      selectedMemoryEntries.slice(0, 6).forEach((entry) => {
        const kind = String(entry?.kind || 'memory');
        const content = String(entry?.content || '').trim();
        const tags = Array.isArray(entry?.tags) ? entry.tags.filter(Boolean) : [];
        const source = String(entry?.source || 'session');
        const card = document.createElement('div');
        card.className = 'rounded border border-white/10 bg-surface p-2';
        card.innerHTML = `
          <div class="flex items-center justify-between gap-2 text-xs uppercase tracking-wide text-text-tertiary">
            <span>${kind}</span>
            <span>${source}</span>
          </div>
          <div class="text-sm text-text-secondary mt-1 whitespace-pre-wrap">${content || '-'}</div>
          <div class="text-xs text-text-tertiary mt-1">${tags.length ? tags.join(', ') : 'no-tags'}</div>
        `;
        roleplayMemoryEl.appendChild(card);
      });
    }
  }

  if (roleplaySceneBeatsEl) {
    roleplaySceneBeatsEl.innerHTML = '';
    if (!selectedSceneBeats.length) {
      roleplaySceneBeatsEl.innerHTML = '<p class="text-sm text-text-tertiary">Keine Scene-Beats vorhanden.</p>';
    } else {
      selectedSceneBeats.slice(0, 6).forEach((beat) => {
        const item = document.createElement('div');
        item.className = 'rounded border border-white/10 bg-surface p-2 text-sm text-text-secondary break-words';
        item.textContent = String(beat);
        roleplaySceneBeatsEl.appendChild(item);
      });
    }
  }

  if (roleplayPromptPreviewMetaEl) {
    const promptChars = Number(roleplayDebug.prompt_preview_chars || 0);
    const historyTurnLimit = Number(roleplayDebug.history_turn_limit || 0);
    const includesToolsSummary = Boolean(roleplayDebug.includes_tools_summary);
    roleplayPromptPreviewMetaEl.textContent = `Zeichen: ${promptChars || 0} · History-Turns: ${historyTurnLimit || 0} · Tools-Summary: ${includesToolsSummary ? 'ja' : 'nein'}`;
  }
  if (roleplayPromptPreviewEl) {
    roleplayPromptPreviewEl.textContent = String(roleplayDebug.prompt_preview || '-');
  }
}

const SESSION_INFO_LABELS = {
  session_id: 'Session-ID',
  status: 'Status',
  language: 'Sprache',
  created_at: 'Erstellt am',
  updated_at: 'Aktualisiert am',
  autonomy_mode: 'Autonomiemodus',
  instruction_style: 'Instruktionsstil',
  desired_intensity: 'Intensität',
  grooming_preference: 'Pflegepräferenz',
  integrations: 'Integrationen',
  hard_stop_enabled: 'Hard-Stop',
  seal_mode: 'Versiegelungsmodus',
  seal_status: 'Versiegelungsstatus',
  seal_current: 'Aktuelle Plombe',
  contract_start: 'Vertragsbeginn',
  contract_end: 'Vertragsende',
  contract_min_end: 'Frühestmögl. Ende',
  contract_max_end: 'Spätestmögl. Ende',
  timer_state: 'Timer-Status',
  timer_end: 'Timer-Ende',
  opening_limit: 'Öffnungslimit',
  opening_window: 'Öffnungsfenster',
  penalty_per_day: 'Max. Strafe/Tag',
  penalty_per_week: 'Max. Strafe/Woche',
  blocked_words: 'Gesperrte Wörter',
  forbidden_topics: 'Verbotene Themen',
};

function fmtDateIso(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
}

function renderSessionInfo(body) {
  const sectionEl = document.getElementById('sessionInfoSection');
  const tbodyEl = document.getElementById('sessionInfoTableBody');
  if (!sectionEl || !tbodyEl) return;

  if (!body?.has_active_session) {
    sectionEl.classList.add('hidden');
    return;
  }

  const sess = body.chastity_session || {};
  const policy = (sess.policy && typeof sess.policy === 'object') ? sess.policy : {};
  const psychogram = (sess.psychogram && typeof sess.psychogram === 'object') ? sess.psychogram : {};
  const contract = (policy.contract && typeof policy.contract === 'object') ? policy.contract : {};
  const limits = (policy.limits && typeof policy.limits === 'object') ? policy.limits : {};
  const interaction = (policy.interaction_profile && typeof policy.interaction_profile === 'object') ? policy.interaction_profile : {};
  const safetyFilters = (policy.safety_filters && typeof policy.safety_filters === 'object') ? policy.safety_filters : {};
  const psychInteraction = (psychogram.interaction_preferences && typeof psychogram.interaction_preferences === 'object')
    ? psychogram.interaction_preferences
    : {};
  const psychPersonal = (psychogram.personal_preferences && typeof psychogram.personal_preferences === 'object')
    ? psychogram.personal_preferences
    : {};
  const timer = (policy.runtime_timer && typeof policy.runtime_timer === 'object') ? policy.runtime_timer : {};
  const seal = (policy.seal && typeof policy.seal === 'object') ? policy.seal : {};
  const runtimeSeal = (policy.runtime_seal && typeof policy.runtime_seal === 'object') ? policy.runtime_seal : {};

  const rows = [
    ['session_id', sess.session_id || '—'],
    ['status', sess.status || '—'],
    ['language', sess.language || '—'],
    ['created_at', fmtDateIso(sess.created_at)],
    ['updated_at', fmtDateIso(sess.updated_at)],
    ['autonomy_mode', policy.autonomy_mode || '—'],
    ['instruction_style', interaction.instruction_style || psychInteraction.instruction_style || '—'],
    ['desired_intensity', psychInteraction.desired_intensity || '—'],
    ['grooming_preference', psychPersonal.grooming_preference || '—'],
    ['integrations', Array.isArray(policy.integrations) && policy.integrations.length ? policy.integrations.join(', ') : '—'],
    ['hard_stop_enabled', policy.hard_stop_enabled != null ? (policy.hard_stop_enabled ? 'Ja' : 'Nein') : '—'],
    ['seal_mode', seal.mode || '—'],
    ['seal_status', runtimeSeal.status || '—'],
    ['seal_current', runtimeSeal.current_text || '—'],
    ['contract_start', contract.start_date || contract.contract_start_date || '—'],
    ['contract_end', contract.end_date || contract.proposed_end_date || '—'],
    ['contract_min_end', contract.min_end_date || '—'],
    ['contract_max_end', contract.max_end_date || '—'],
    ['timer_state', timer.state || '—'],
    ['timer_end', fmtDateIso(timer.effective_end_at)],
    ['opening_limit', limits.max_openings_in_period != null ? `${limits.max_openings_in_period} / ${limits.opening_limit_period || 'Tag'}` : '—'],
    ['opening_window', limits.opening_window_minutes != null ? `${limits.opening_window_minutes} Min.` : '—'],
    ['penalty_per_day', limits.max_penalty_per_day_minutes != null ? `${limits.max_penalty_per_day_minutes} Min.` : '—'],
    ['penalty_per_week', limits.max_penalty_per_week_minutes != null ? `${limits.max_penalty_per_week_minutes} Min.` : '—'],
    ['blocked_words', Array.isArray(safetyFilters.blocked_trigger_words) && safetyFilters.blocked_trigger_words.length ? safetyFilters.blocked_trigger_words.join(', ') : '—'],
    ['forbidden_topics', Array.isArray(safetyFilters.forbidden_topics) && safetyFilters.forbidden_topics.length ? safetyFilters.forbidden_topics.join(', ') : '—'],
  ];

  tbodyEl.innerHTML = '';
  rows.forEach(([key, value]) => {
    const tr = document.createElement('tr');
    tr.className = 'align-top';
    tr.innerHTML = `
      <td class="py-2 pr-4 text-text-tertiary font-medium whitespace-nowrap w-1/3">${SESSION_INFO_LABELS[key] || key}</td>
      <td class="py-2 text-text break-all">${String(value)}</td>
    `;
    tbodyEl.appendChild(tr);
  });

  sectionEl.classList.remove('hidden');
}

function describeActiveSession(body) {
  if (!body) return '—';
  if (body.has_active_session) {
    const sess = body.chastity_session || {};
    return sess.session_id || sess.id || 'active (unknown id)';
  }
  return 'Keine aktive Session';
}

function describeSetup(body) {
  if (!body) return '—';
  const status = body.setup_status || 'unknown';
  const id = body.setup_session_id || 'n/a';
  return `${status} (${id})`;
}

function updateView(body) {
  currentSession = body;
  if (activeEl) activeEl.textContent = describeActiveSession(body);
  if (setupEl) setupEl.textContent = describeSetup(body);
  // Hide skeletons and show actual content
  const countdownSkeleton = document.getElementById('countdownSkeleton');
  const countdownActual = document.getElementById('countdownActual');
  if (countdownSkeleton) countdownSkeleton.classList.add('hidden');
  if (countdownActual) countdownActual.classList.remove('hidden');
  const activeSessionSkeleton = document.getElementById('activeSessionSkeleton');
  const setupSessionSkeleton = document.getElementById('setupSessionSkeleton');
  if (activeSessionSkeleton) activeSessionSkeleton.classList.add('hidden');
  if (setupSessionSkeleton) setupSessionSkeleton.classList.add('hidden');
  renderTimer(body);
  renderOpeningLimit(body);
  renderSessionInfo(body);
  renderPsychogram(body);
  renderRoleplay(body);

  if (statusEl) {
    const msg = body?.has_active_session ? 'Session status loaded.' : 'Keine aktive Session. Setup fortsetzen.';
    chastease_common.setStatus(statusEl, msg, body?.has_active_session ? 'ok' : 'err');
  }
}

function refreshSession(forceRefresh = false) {
  if (!sessionHelper || typeof sessionHelper.fetchActiveSession !== 'function') {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session helper missing.', 'err');
    return;
  }
  sessionHelper.fetchActiveSession(statusEl, { forceRefresh }).then((body) => {
    if (!body) return;
    updateView(body);
  });
}

function shouldRunSessionRefresh() {
  if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return false;
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return false;
  return true;
}

function startSessionAutoRefresh() {
  if (sessionRefreshInterval) return;
  sessionRefreshInterval = window.setInterval(() => {
    if (!shouldRunSessionRefresh()) return;
    refreshSession(false);
  }, SESSION_AUTO_REFRESH_MS);
}

function goToSetup() {
  const setupId = currentSession?.setup_session_id;
  const target = setupId ? `/setup?setup_session_id=${encodeURIComponent(setupId)}` : '/setup';
  window.location.href = target;
}

function killSession() {
  if (!currentSession) return;
  const auth = sessionHelper?.getStoredAuth();
  if (!auth) {
    if (statusEl) chastease_common.setStatus(statusEl, 'No auth info.', 'err');
    return;
  }
  if (statusEl) chastease_common.setStatus(statusEl, 'Deleting session...');
  fetch(`/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`, {
    method: 'DELETE',
  })
    .then((res) => res.json().then((body) => ({ status: res.status, body })))
    .then(({ status, body }) => {
      if (status === 200) {
        if (sessionHelper && typeof sessionHelper.invalidateActiveSessionCache === 'function') {
          sessionHelper.invalidateActiveSessionCache();
        }
        if (statusEl) chastease_common.setStatus(statusEl, 'Session deleted.');
        refreshSession(true);
      } else if (statusEl) {
        chastease_common.setStatus(statusEl, body.detail || 'Failed to delete', 'err');
      }
    })
    .catch(() => statusEl && chastease_common.setStatus(statusEl, 'Delete request failed', 'err'));
}

function openAuditLog() {
  if (!currentSession?.has_active_session) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Keine aktive Session.', 'err');
    return;
  }
  const sessionEntity = currentSession.chastity_session || {};
  const sessionId = sessionEntity.session_id || sessionEntity.id;
  if (!sessionId) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session-ID fehlt.', 'err');
    return;
  }
  if (statusEl) chastease_common.setStatus(statusEl, 'Audit-Log wird geöffnet.');
  const target = `/audit-log?session_id=${encodeURIComponent(sessionId)}`;
  const win = window.open(target, '_blank');
  if (!win) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Popup blockiert.', 'err');
    return;
  }
  win.focus?.();
  if (statusEl) chastease_common.setStatus(statusEl, 'Audit-Log geöffnet.', 'ok');
}

function openTurnLog() {
  if (!currentSession?.has_active_session) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Keine aktive Session.', 'err');
    return;
  }
  const sessionEntity = currentSession.chastity_session || {};
  const sessionId = sessionEntity.session_id || sessionEntity.id;
  if (!sessionId) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session-ID fehlt.', 'err');
    return;
  }
  if (statusEl) chastease_common.setStatus(statusEl, 'Turn-Log wird geöffnet.');
  const target = `/turn-log?session_id=${encodeURIComponent(sessionId)}`;
  const win = window.open(target, '_blank');
  if (!win) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Popup blockiert.', 'err');
    return;
  }
  win.focus?.();
  if (statusEl) chastease_common.setStatus(statusEl, 'Turn-Log geöffnet.', 'ok');
}

function openActivityLog() {
  if (!currentSession?.has_active_session) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Keine aktive Session.', 'err');
    return;
  }
  const sessionEntity = currentSession.chastity_session || {};
  const sessionId = sessionEntity.session_id || sessionEntity.id;
  if (!sessionId) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session-ID fehlt.', 'err');
    return;
  }
  if (statusEl) chastease_common.setStatus(statusEl, 'Activity-Log wird geöffnet.');
  const target = `/activity-log?session_id=${encodeURIComponent(sessionId)}`;
  const win = window.open(target, '_blank');
  if (!win) {
    if (statusEl) chastease_common.setStatus(statusEl, 'Popup blockiert.', 'err');
    return;
  }
  win.focus?.();
  if (statusEl) chastease_common.setStatus(statusEl, 'Activity-Log geöffnet.', 'ok');
}

if (refreshBtn) refreshBtn.addEventListener('click', () => refreshSession(true));
if (setupBtn) setupBtn.addEventListener('click', goToSetup);
if (killBtn) killBtn.addEventListener('click', killSession);
if (auditBtn) auditBtn.addEventListener('click', openAuditLog);
if (turnLogBtn) turnLogBtn.addEventListener('click', openTurnLog);
if (activityLogBtn) activityLogBtn.addEventListener('click', openActivityLog);

document.addEventListener('visibilitychange', () => {
  if (!shouldRunSessionRefresh()) return;
  refreshSession(true);
});

document.addEventListener('DOMContentLoaded', () => {
  if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
    chastease_common.renderNavAuth();
  }
  refreshSession(true);
  startSessionAutoRefresh();
});
