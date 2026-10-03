"use client";

import { useEffect, useMemo, useState } from "react";

type SignalKey = "sleep" | "load" | "connection" | "movement" | "mood";
type ScenarioName = "Steady week" | "Quiet drift" | "High strain" | "Signal without meaning" | "Flat physiology, hard week";

const presets: Record<ScenarioName, Record<SignalKey, number>> = {
  "Steady week": { sleep: 78, load: 32, connection: 70, movement: 68, mood: 74 },
  "Quiet drift": { sleep: 52, load: 67, connection: 38, movement: 44, mood: 51 },
  "High strain": { sleep: 34, load: 88, connection: 24, movement: 30, mood: 35 },
  "Signal without meaning": { sleep: 22, load: 82, connection: 18, movement: 24, mood: 58 },
  "Flat physiology, hard week": { sleep: 75, load: 38, connection: 69, movement: 71, mood: 22 },
};

const scenarioMeta: Record<ScenarioName, {
  headline: string;
  insight: string;
  starter: string;
  consensus: "Fits" | "Mostly fits" | "Doesn’t fit";
  participantPattern: string;
  participantContext: string;
  clinicianTrajectory: string;
  clinicianConfidence: string;
  clinicianPrompt: string;
  validation: string;
}> = {
  "Steady week": {
    headline: "Your week looks close to baseline.",
    insight: "Sleep, connection, movement, and check-in mood are moving within Srivahni’s usual range. No single signal is treated as the answer.",
    starter: "“What helped this week feel more workable?”",
    consensus: "Fits",
    participantPattern: "“This mostly looks like an ordinary week.”",
    participantContext: "No major exception this week. The routine felt boring in a useful way.",
    clinicianTrajectory: "Steady +4%",
    clinicianConfidence: "Moderate 4 of 5 signals",
    clinicianPrompt: "“What made the steadier days possible?”",
    validation: "Check-in, session reflection, and next-week stability should broadly agree.",
  },
  "Quiet drift": {
    headline: "Your week is asking for attention, not judgment.",
    insight: "Later, less consistent sleep overlaps with a quieter social rhythm. Srivahni marked her mood lower on the same days.",
    starter: "“What felt different around Wednesday, and what helped, even a little?”",
    consensus: "Mostly fits",
    participantPattern: "“My routine became less steady after Tuesday.”",
    participantContext: "The change started after a difficult conversation at work. I still went for a walk on Thursday, which helped.",
    clinicianTrajectory: "Watchful -9%",
    clinicianConfidence: "Moderate 3 of 5 signals",
    clinicianPrompt: "“You connected the shift to a difficult conversation. What did Thursday’s walk change for you?”",
    validation: "The claim holds only if Srivahni’s check-in and the session narrative confirm that the shift mattered.",
  },
  "High strain": {
    headline: "A meaningful shift worth exploring together.",
    insight: "Mental load is elevated while sleep, movement, and social contact are all below Srivahni’s baseline. The system should treat this as a question, not a diagnosis.",
    starter: "“What has been carrying the most load this week?”",
    consensus: "Mostly fits",
    participantPattern: "“This was a high-strain week.”",
    participantContext: "Work pressure was intense, and I cancelled plans twice. I want to talk about what felt unmanageable.",
    clinicianTrajectory: "Needs attention -18%",
    clinicianConfidence: "Higher 5 of 5 signals",
    clinicianPrompt: "“Where did the week start to feel less manageable?”",
    validation: "A stronger flag needs convergence across check-in, context, clinician judgment, and short-term follow-up.",
  },
  "Signal without meaning": {
    headline: "The signal is loud. The meaning is wrong.",
    insight: "Passive signals show disrupted sleep, movement, and social contact after travel. Srivahni marks the interpretation as not fitting: she flew to a funeral, so the shift is contextual grief and logistics, not a hidden deterioration pattern.",
    starter: "“What did the model miss about why the week changed?”",
    consensus: "Doesn’t fit",
    participantPattern: "“My routine collapsed, but the explanation is wrong.”",
    participantContext: "I flew to a funeral. Sleep, movement, and social time were all unusual for obvious reasons. Please don’t learn this as my baseline.",
    clinicianTrajectory: "Flagged, then corrected",
    clinicianConfidence: "Low after context",
    clinicianPrompt: "“What should be excluded from the pattern, and what still needs support?”",
    validation: "A correct system must absorb the correction: down-weight this week, retain Srivahni’s context, and avoid treating the funeral week as evidence of the same pattern later.",
  },
  "Flat physiology, hard week": {
    headline: "Passive data says steady. Srivahni says otherwise.",
    insight: "Sleep, movement, and social contact look normal, so a sensor-only model would miss the week. The concern appears only because Srivahni’s check-in reports a sharp mood drop.",
    starter: "“What felt worse even though your routine looked normal?”",
    consensus: "Fits",
    participantPattern: "“The data looked fine, but I was not fine.”",
    participantContext: "I kept doing the usual things and still felt much worse. The check-in is the only place that captured it.",
    clinicianTrajectory: "No passive flag",
    clinicianConfidence: "Low 1 of 5 signals",
    clinicianPrompt: "“What was harder internally, even while the outside routine stayed intact?”",
    validation: "This is validated against Srivahni’s check-in and clinical conversation, not passive physiology. The miss should be visible in model review.",
  },
};

const signalMeta: Array<{ key: SignalKey; label: string; low: string; high: string }> = [
  { key: "sleep", label: "Sleep regularity", low: "Fragmented", high: "Consistent" },
  { key: "load", label: "Mental load", low: "Light", high: "Intense" },
  { key: "connection", label: "Social connection", low: "Withdrawn", high: "Connected" },
  { key: "movement", label: "Movement", low: "Limited", high: "Restorative" },
  { key: "mood", label: "Mood check-in", low: "Low", high: "Grounded" },
];

const walkthroughSteps = [
  {
    time: "00:08",
    label: "Before the session",
    title: "A pattern becomes visible",
    copy: "Srivahni notices that sleep timing, connection, and mood shifted together—not just that she had a ‘bad week.’",
  },
  {
    time: "00:24",
    label: "Srivahni adds context",
    title: "The person completes the picture",
    copy: "She confirms what fits, corrects what does not, and chooses the insights she wants to bring into therapy.",
  },
  {
    time: "00:43",
    label: "During the session",
    title: "Shared context, deeper conversation",
    copy: "Dr. Chen starts with Srivahni’s reflection and the uncertain pattern—leaving more time for meaning, not reconstruction.",
  },
  {
    time: "01:06",
    label: "After the session",
    title: "A small plan carries forward",
    copy: "Together they note one protective routine to observe. The model learns only from feedback Srivahni has consented to share.",
  },
];

function Sparkline({ values, tone = "teal" }: { values: number[]; tone?: "teal" | "coral" }) {
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${100 - value}`).join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Seven day wellness trajectory" role="img">
      <defs>
        <linearGradient id={`fill-${tone}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={tone === "teal" ? "#198f86" : "#e26f55"} stopOpacity=".24" />
          <stop offset="1" stopColor={tone === "teal" ? "#198f86" : "#e26f55"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`M0,100 L${points} L100,100 Z`} fill={`url(#fill-${tone})`} />
      <polyline points={points} fill="none" stroke={tone === "teal" ? "#198f86" : "#e26f55"} strokeWidth="3" vectorEffect="non-scaling-stroke" />
      {values.map((value, index) => (
        <circle key={index} cx={(index / (values.length - 1)) * 100} cy={100 - value} r="2.8" fill="#fff" stroke={tone === "teal" ? "#198f86" : "#e26f55"} strokeWidth="1.8" vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  );
}

export default function Home() {
  const [signals, setSignals] = useState<Record<SignalKey, number>>(presets["Quiet drift"]);
  const [activePreset, setActivePreset] = useState<ScenarioName>("Quiet drift");
  const [perspective, setPerspective] = useState<"participant" | "psychologist">("participant");
  const [walkthroughStep, setWalkthroughStep] = useState(0);
  const [walkthroughPlaying, setWalkthroughPlaying] = useState(false);
  const [consensusChoice, setConsensusChoice] = useState("Mostly fits");

  useEffect(() => {
    if (!walkthroughPlaying) return;
    const timer = window.setInterval(() => {
      setWalkthroughStep(current => {
        if (current === walkthroughSteps.length - 1) {
          setWalkthroughPlaying(false);
          return 0;
        }
        return current + 1;
      });
    }, 3600);
    return () => window.clearInterval(timer);
  }, [walkthroughPlaying]);

  const state = useMemo(() => {
    if (activePreset === "Signal without meaning") {
      return { score: 31, level: "Flagged", delta: "-21", color: "#d9584c", trend: [74, 70, 39, 24, 29, 32, 31] };
    }
    if (activePreset === "Flat physiology, hard week") {
      return { score: 72, level: "Steady?", delta: "+1", color: "#d47b32", trend: [71, 72, 72, 73, 71, 72, 72] };
    }
    const protective = signals.sleep * .27 + signals.connection * .18 + signals.movement * .15 + signals.mood * .3;
    const score = Math.round(Math.max(12, Math.min(92, protective + (100 - signals.load) * .1)));
    const level = score >= 68 ? "Steady" : score >= 48 ? "Watchful" : "Needs attention";
    const delta = score >= 68 ? "+4" : score >= 48 ? "−9" : "−18";
    const color = score >= 68 ? "#198f86" : score >= 48 ? "#d47b32" : "#d9584c";
    const trend = [score + 16, score + 13, score + 11, score + 8, score + 6, score + 2, score].map(v => Math.max(8, Math.min(94, v)));
    return { score, level, delta, color, trend };
  }, [activePreset, signals]);

  const activeMeta = scenarioMeta[activePreset];

  const applyPreset = (name: ScenarioName) => {
    setActivePreset(name);
    setSignals(presets[name]);
    setConsensusChoice(scenarioMeta[name].consensus);
  };

  return (
    <main>
      <nav className="topbar">
        <a className="brand" href="#top" aria-label="PsycheTrajectory home">
          <span className="brand-mark"><i /><i /><i /></span>
          <span>PsycheTrajectory</span>
        </a>
        <div className="nav-links">
          <a href="#simulator">Simulator</a>
          <a href="#approach">How it works</a>
          <a href="#walkthrough">Session walkthrough</a>
        </div>
        <a className="nav-cta" href="#simulator">Try the demo <span>↗</span></a>
      </nav>

      <section className="hero" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span /> A shared language for what changes between sessions</div>
          <h1>See the pattern.<br /><em>Hear the person.</em></h1>
          <p className="hero-lede">
            PsycheTrajectory turns everyday wellbeing signals into a clear, explainable story—helping people and psychologists begin each session with shared context, not a blank page.
          </p>
          <div className="hero-actions">
            <a href="#simulator" className="button primary">Explore the simulator <span>→</span></a>
            <a href="#walkthrough" className="button ghost"><span className="play-icon">▶</span> Watch 72-sec walkthrough</a>
          </div>
          <div className="trust-line">
            <span><b>01</b> Not a diagnosis</span>
            <span><b>02</b> Human-confirmed</span>
            <span><b>03</b> Privacy-conscious</span>
          </div>
        </div>

        <div className="hero-visual" aria-label="Example wellbeing trajectory dashboard">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <article className="preview-card">
            <header className="preview-header">
              <div>
                <span className="mini-label">THIS WEEK · AUG 3–9</span>
                <h3>Good morning, Srivahni</h3>
              </div>
              <div className="avatar">S</div>
            </header>
            <div className="state-summary">
              <div className="score-ring" style={{ "--score": "62", "--ring": "#e18745" } as React.CSSProperties}>
                <div><strong>62</strong><small>of 100</small></div>
              </div>
              <div>
                <span className="status watchful">WATCHFUL</span>
                <h4>Your rhythm shifted this week</h4>
                <p>Lower sleep consistency and fewer social moments appear to be moving together.</p>
              </div>
            </div>
            <div className="mini-chart">
              <div className="chart-meta"><span>7-day trajectory</span><strong>−9 <small>from baseline</small></strong></div>
              <Sparkline values={[76, 74, 71, 68, 66, 63, 62]} tone="coral" />
              <div className="days"><span>M</span><span>T</span><span>W</span><span>T</span><span>F</span><span>S</span><span>S</span></div>
            </div>
            <div className="context-prompt">
              <span className="prompt-icon">✦</span>
              <p><b>Does this feel right?</b><br />Add your context before Friday’s session.</p>
              <button aria-label="Add context">＋</button>
            </div>
          </article>
          <aside className="signal-float"><span>Moon</span><div><b>Sleep timing</b><small>46 min later than usual</small></div></aside>
          <aside className="consent-float"><span>✓</span><div><b>You choose what’s shared</b><small>3 insights selected for Dr. Chen</small></div></aside>
        </div>
      </section>

      <section className="pitch-strip" aria-label="Elevator pitch">
        <span>THE IDEA IN 15 SECONDS</span>
        <p>Therapy sees a moment. Life happens between moments. <b>PsycheTrajectory helps connect the two.</b></p>
      </section>

      <section className="simulator-section" id="simulator">
        <div className="section-heading">
          <div><span className="section-index">01 / LIVE SIMULATOR</span><h2>Move the signals.<br />See the story change.</h2></div>
          <p>This is an illustrative model—not a clinical score. Adjust the week below to see how raw signals become an explainable trajectory and a better conversation.</p>
        </div>

        <div className="simulator-shell">
          <div className="controls-panel">
            <div className="preset-row">
              <span>Try a scenario</span>
              <div>{(Object.keys(presets) as ScenarioName[]).map(name => <button key={name} onClick={() => applyPreset(name)} className={activePreset === name ? "active" : ""}>{name}</button>)}</div>
            </div>
            <div className="slider-list">
              {signalMeta.map(item => (
                <label className="signal-control" key={item.key}>
                  <div><span>{item.label}</span><strong>{signals[item.key]}%</strong></div>
                  <input
                    type="range" min="0" max="100" value={signals[item.key]}
                    onChange={(event) => {
                      setSignals(current => ({ ...current, [item.key]: Number(event.target.value) }));
                    }}
                    style={{ "--value": `${signals[item.key]}%` } as React.CSSProperties}
                    aria-label={item.label}
                  />
                  <div className="range-labels"><span>{item.low}</span><span>{item.high}</span></div>
                </label>
              ))}
            </div>
            <p className="sim-note"><span>i</span> In a real deployment, users control which device, journal, and check-in signals contribute.</p>
          </div>

          <div className="output-panel">
            <div className="perspective-toggle" role="group" aria-label="Choose perspective">
              <button className={perspective === "participant" ? "active" : ""} onClick={() => setPerspective("participant")}>Participant view</button>
              <button className={perspective === "psychologist" ? "active" : ""} onClick={() => setPerspective("psychologist")}>Psychologist view</button>
            </div>
            <div className="output-top">
              <div className="dynamic-score" style={{ borderColor: state.color }}><strong>{state.score}</strong><span>Trajectory<br />index</span></div>
              <div><span className="dynamic-status" style={{ color: state.color, backgroundColor: `${state.color}14` }}>{state.level}</span><h3>{activeMeta.headline}</h3></div>
            </div>
            <div className="output-chart">
              <div className="chart-meta"><span>Relative to personal baseline</span><strong style={{ color: state.color }}>{state.delta}%</strong></div>
              <Sparkline values={state.trend} tone={state.score >= 68 ? "teal" : "coral"} />
              <div className="days"><span>Aug 3</span><span>4</span><span>5</span><span>6</span><span>7</span><span>8</span><span>Today</span></div>
            </div>
            <div className="interpretation">
              <span className="interpret-icon">✦</span>
              <div>
                <small>EXPLAINABLE INSIGHT</small>
                <p>{activeMeta.insight}</p>
              </div>
            </div>
            <div className="validation-panel">
              <small>HOW WE’D KNOW IF THIS IS TRUE</small>
              <p>{activeMeta.validation}</p>
            </div>
            <div className="conversation-starter">
              <small>{perspective === "participant" ? "YOUR CONTEXT" : "SESSION STARTER"}</small>
              <p>{activeMeta.starter}</p>
              <button>{perspective === "participant" ? "Add my reflection" : "Add to session notes"} <span>→</span></button>
            </div>
          </div>
        </div>
      </section>

      <section className="approach-section" id="approach">
        <div className="approach-intro">
          <span className="section-index">02 / HOW IT WORKS</span>
          <h2>From many signals<br />to one <em>human story.</em></h2>
          <p>The system separates observation from interpretation. Every layer stays inspectable, personal-baseline aware, and open to correction.</p>
        </div>
        <div className="pipeline" aria-label="Signals to support pipeline">
          {[
            ["01", "Signals", "Sleep · routine · movement · check-ins"],
            ["02", "Features", "Timing · variability · direction · context"],
            ["03", "Latent state", "A probabilistic, evolving representation"],
            ["04", "Trajectory", "Meaningful change against personal baseline"],
            ["05", "Risk", "Uncertainty-aware flags, never a diagnosis"],
            ["06", "Support", "Reflection · conversation · timely care"],
          ].map(([index, title, copy]) => (
            <article key={title}>
              <span>{index}</span>
              <div className="pipeline-icon"><i /><i /><i /></div>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
        <div className="guardrail-row">
          <div><span className="guard-icon">◌</span><p><b>Personal, not population-default</b><br />Change is compared with the person’s own patterns wherever possible.</p></div>
          <div><span className="guard-icon">≈</span><p><b>Uncertainty stays visible</b><br />Confidence and missing context remain part of every interpretation.</p></div>
          <div><span className="guard-icon">✓</span><p><b>Confirmed by the human</b><br />The model proposes. The person and professional interpret together.</p></div>
        </div>
      </section>

      <section className="consensus-section">
        <div className="section-heading consensus-heading">
          <div><span className="section-index">03 / SHARED CONSENSUS</span><h2>One trajectory.<br />Two viewpoints.</h2></div>
          <p>Consensus is not forced agreement. It is a structured way to compare the model’s suggestion, the person’s lived experience, and the psychologist’s clinical judgment.</p>
        </div>
        <div className="consensus-board">
          <article className="view-card participant-card">
            <header><div className="avatar warm">S</div><div><small>PARTICIPANT</small><h3>Srivahni’s view</h3></div><span>Private until shared</span></header>
            <div className="view-body">
              <span className="card-kicker">PROPOSED PATTERN</span>
              <h4>{activeMeta.participantPattern}</h4>
              <p>{activePreset === "Signal without meaning" ? "The system noticed a hard passive-signal deviation, then Srivahni rejected the proposed meaning." : activePreset === "Flat physiology, hard week" ? "The system did not see a passive-signal shift. Srivahni’s check-in is the alert." : "The system noticed later sleep, lower movement, and fewer social moments."}</p>
              <div className="feedback-options" role="group" aria-label="Does this insight fit?">
                {["Fits", "Mostly fits", "Doesn’t fit"].map(choice => <button key={choice} className={consensusChoice === choice ? "active" : ""} onClick={() => setConsensusChoice(choice)}>{choice === "Fits" ? "✓" : choice === "Mostly fits" ? "~" : "×"} {choice}</button>)}
              </div>
              <label className="reflection-box"><span>MY CONTEXT</span><p>{activeMeta.participantContext}</p></label>
            </div>
          </article>

          <div className="consensus-bridge">
            <span className="bridge-line" />
            <div><span>✓</span><small>SHARED<br />CONTEXT</small></div>
            <span className="bridge-line" />
          </div>

          <article className="view-card clinician-card">
            <header><div className="avatar clinician">DC</div><div><small>PSYCHOLOGIST</small><h3>Dr. Chen’s view</h3></div><span>With Srivahni’s consent</span></header>
            <div className="view-body">
              <div className="clinician-row"><span>TRAJECTORY</span><b>{activeMeta.clinicianTrajectory}</b></div>
              <div className="clinician-row"><span>CONFIDENCE</span><b>{activeMeta.clinicianConfidence}</b></div>
              <div className="session-question">
                <small>SUGGESTED OPENING</small>
                <p>{activeMeta.clinicianPrompt}</p>
              </div>
              <div className="clinical-actions"><button>Keep for session</button><button>View signal rationale</button></div>
            </div>
          </article>
        </div>
        <p className="consensus-caption"><span>✦</span> The shared view preserves disagreement: <b>Srivahni’s correction is data, not noise.</b></p>
      </section>

      <section className="walkthrough-section" id="walkthrough">
        <div className="walkthrough-copy">
          <span className="section-index">04 / SESSION WALKTHROUGH</span>
          <h2>More time for<br /><em>meaning.</em></h2>
          <p>A short concept walkthrough of how PsycheTrajectory can augment—not replace—the therapeutic relationship.</p>
          <div className="step-list">
            {walkthroughSteps.map((step, index) => (
              <button key={step.label} className={walkthroughStep === index ? "active" : ""} onClick={() => { setWalkthroughStep(index); setWalkthroughPlaying(false); }}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><b>{step.label}</b><small>{step.title}</small></div>
              </button>
            ))}
          </div>
        </div>

        <div className="concept-film">
          <div className="film-top"><span>PSYCHETRAJECTORY · CONCEPT FILM</span><span>{walkthroughSteps[walkthroughStep].time} / 01:12</span></div>
          <div className={`film-stage scene-${walkthroughStep}`}>
            <div className="film-glow" />
            {walkthroughStep === 0 && (
              <div className="scene-card phone-scene"><div className="phone-notch" /><small>YOUR WEEK</small><div className="scene-score">62</div><b>A shift worth noticing</b><span className="micro-line long" /><span className="micro-line" /><div className="tiny-chart"><i /><i /><i /><i /><i /><i /></div></div>
            )}
            {walkthroughStep === 1 && (
              <div className="scene-card context-scene"><span className="scene-chip">Mostly fits</span><h4>What was happening?</h4><p>“A difficult conversation at work changed my rhythm…”</p><div className="share-row"><span>✓ Share with Dr. Chen</span><b>Selected</b></div></div>
            )}
            {walkthroughStep === 2 && (
              <div className="therapy-scene"><div className="person person-one"><span>S</span></div><div className="session-screen"><small>SHARED FOR TODAY</small><b>What changed around Wednesday?</b><div className="session-wave"><i /><i /><i /><i /><i /></div></div><div className="person person-two"><span>DC</span></div></div>
            )}
            {walkthroughStep === 3 && (
              <div className="scene-card plan-scene"><span className="plan-check">✓</span><small>ONE THING TO CARRY FORWARD</small><h4>Notice what changes after an evening walk.</h4><div><span>Observe for 7 days</span><span>Srivahni controls sharing</span></div></div>
            )}
            <div className="film-caption"><small>{walkthroughSteps[walkthroughStep].label}</small><h3>{walkthroughSteps[walkthroughStep].title}</h3><p>{walkthroughSteps[walkthroughStep].copy}</p></div>
          </div>
          <div className="film-controls">
            <button className="film-play" onClick={() => setWalkthroughPlaying(value => !value)} aria-label={walkthroughPlaying ? "Pause walkthrough" : "Play walkthrough"}>{walkthroughPlaying ? "Ⅱ" : "▶"}</button>
            <div className="film-progress"><span style={{ width: `${((walkthroughStep + 1) / walkthroughSteps.length) * 100}%` }} /></div>
            <span>{walkthroughPlaying ? "PLAYING" : "PAUSED"}</span>
          </div>
        </div>
      </section>

      <section className="outcomes-section">
        <span className="section-index">WHAT THIS CHANGES IN THE ROOM</span>
        <div className="outcome-grid">
          <article><strong>01</strong><h3>Less recall burden</h3><p>The person does not have to reconstruct an entire week from memory in the first ten minutes.</p></article>
          <article><strong>02</strong><h3>More precise curiosity</h3><p>Patterns become questions to explore—not conclusions imposed on the person.</p></article>
          <article><strong>03</strong><h3>Continuity over time</h3><p>Small protective factors and meaningful shifts remain visible across sessions.</p></article>
        </div>
      </section>

      <section className="final-cta">
        <div className="cta-orbit"><i /><i /><i /></div>
        <span>PILOT CONVERSATION</span>
        <h2>Help shape a tool that<br />listens <em>between sessions.</em></h2>
        <p>This prototype is designed to invite critique from psychologists and people with lived experience before clinical claims are made.</p>
        <div><a href="#simulator" className="button primary">Run the simulator again <span>↑</span></a><button className="button light">Share clinical feedback <span>→</span></button></div>
      </section>

      <footer>
        <a className="brand" href="#top"><span className="brand-mark"><i /><i /><i /></span><span>PsycheTrajectory</span></a>
        <p><b>Important:</b> This concept is not a medical device, diagnostic instrument, crisis service, or substitute for professional care. Prototype data and outputs are illustrative.</p>
        <span>EARLY CONCEPT · 2026</span>
      </footer>
    </main>
  );
}
