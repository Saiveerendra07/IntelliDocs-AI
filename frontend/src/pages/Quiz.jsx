import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Clock,
  CheckCircle2,
  XCircle,
  Bookmark,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Award,
  Sparkles,
} from 'lucide-react';
import { quizApi } from '../api/quiz';

export const Quiz = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({}); // { [qId]: selectedAnswer }
  const [textInputs, setTextInputs] = useState({}); // { [qId]: string }
  const [evaluations, setEvaluations] = useState({}); // { [qId]: serverEvaluationResponse }
  const [evaluating, setEvaluating] = useState({}); // { [qId]: boolean }
  const [locked, setLocked] = useState({}); // { [qId]: boolean }
  const [markedForReview, setMarkedForReview] = useState(new Set());
  const [timeLeft, setTimeLeft] = useState(600);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const initQuiz = async () => {
      setLoading(true);
      try {
        const quizData = await quizApi.getQuiz(id);
        setQuiz(quizData);
        setQuestions(quizData.questions || []);
        setTimeLeft(quizData.time_limit_seconds || (quizData.questions?.length || 10) * 60);

        const attempt = await quizApi.startAttempt(id);
        setAttemptId(attempt.id);
      } catch (err) {
        console.error('Failed to initialize quiz:', err);
      } finally {
        setLoading(false);
      }
    };
    initQuiz();
  }, [id]);

  useEffect(() => {
    if (timeLeft <= 0) {
      handleSubmitQuiz();
      return;
    }
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft]);

  const currentQ = questions[currentIndex];
  const isCurrentLocked = !!locked[currentQ?.id];
  const currentSelected = answers[currentQ?.id];
  const currentEval = evaluations[currentQ?.id];
  const isEvaluating = !!evaluating[currentQ?.id];

  const handleAnswerSubmit = async (qId, answerValue) => {
    if (!answerValue || locked[qId] || evaluating[qId]) return;

    setAnswers((prev) => ({ ...prev, [qId]: answerValue }));
    setEvaluating((prev) => ({ ...prev, [qId]: true }));

    try {
      const evalRes = await quizApi.submitQuestionResponse(
        attemptId,
        qId,
        answerValue,
        markedForReview.has(qId)
      );
      setEvaluations((prev) => ({ ...prev, [qId]: evalRes }));
      setLocked((prev) => ({ ...prev, [qId]: true }));
    } catch (err) {
      console.error('Server answer evaluation failed:', err);
      // Offline / fallback lock
      setLocked((prev) => ({ ...prev, [qId]: true }));
    } finally {
      setEvaluating((prev) => ({ ...prev, [qId]: false }));
    }
  };

  const toggleMarkForReview = () => {
    if (!currentQ) return;
    setMarkedForReview((prev) => {
      const next = new Set(prev);
      if (next.has(currentQ.id)) {
        next.delete(currentQ.id);
      } else {
        next.add(currentQ.id);
      }
      return next;
    });
  };

  const handleSubmitQuiz = async () => {
    if (submitting) return;

    setSubmitting(true);
    try {
      const formattedResponses = questions.map((q) => ({
        quiz_question_id: q.id,
        selected_answer: answers[q.id] || null,
        marked_for_review: markedForReview.has(q.id),
      }));

      const timeTaken = (quiz?.time_limit_seconds || 600) - timeLeft;
      await quizApi.submitAttempt(attemptId, formattedResponses, Math.max(timeTaken, 1));
      navigate(`/attempts/${attemptId}/results`);
    } catch (err) {
      console.error('Quiz submission failed:', err);
      alert('Submission error: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  const answeredCount = Object.keys(locked).length;
  const progressPercent = Math.round(((currentIndex + 1) / (questions.length || 1)) * 100);
  const qType = (currentQ?.type || 'mcq').toLowerCase();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 sm:px-6 shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-white">
            {quiz?.title || 'Interactive Quiz'}
          </h1>
          <p className="text-xs text-slate-400">
            One question at a time • Instant feedback on click • Progress saved to database
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-center rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 px-3 py-1.5 text-amber-700 dark:text-amber-300 font-mono text-sm font-bold">
          <Clock className="h-4 w-4" />
          <span>{formatTime(timeLeft)}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Question & Immediate Feedback Card */}
        <div className="lg:col-span-3 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 md:p-8 shadow-sm flex flex-col justify-between min-h-[500px]">
          <div>
            {/* Question Progress Header */}
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-2">
              <span className="font-bold text-primary-600 dark:text-primary-400">
                Question {currentIndex + 1} of {questions.length}
              </span>
              <span>{Math.round((answeredCount / (questions.length || 1)) * 100)}% Answered</span>
            </div>

            {/* Linear Progress Bar */}
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden mb-6">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Question Stem */}
            <div className="mb-6 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-primary-100 text-primary-800 dark:bg-primary-950/60 dark:text-primary-300">
                  {currentQ?.type?.replace('_', ' ') || 'Multiple Choice'}
                </span>
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {currentQ?.difficulty || 'Medium'}
                </span>
              </div>
              <h2 className="text-base md:text-lg font-bold text-slate-900 dark:text-white leading-relaxed">
                {currentQ?.question}
              </h2>
            </div>

            {/* MCQ Type: 4 options, single choice */}
            {qType === 'mcq' && (
              <div className="space-y-3">
                {(currentQ?.options || []).map((opt, i) => {
                  const isSelected = currentSelected === opt;
                  const isCorrect = currentEval?.correct_answer === opt;

                  let optClass = 'border-slate-200 dark:border-surface-darkBorder bg-slate-50/40 dark:bg-slate-900/40 text-slate-800 dark:text-slate-200 hover:border-slate-300';
                  let iconClass = 'border-slate-300 dark:border-slate-600 text-slate-400';

                  if (isCurrentLocked) {
                    if (isCorrect) {
                      optClass = 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-100 ring-1 ring-emerald-500 font-semibold';
                      iconClass = 'border-emerald-500 bg-emerald-500 text-white';
                    } else if (isSelected && !isCorrect) {
                      optClass = 'border-rose-500 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-100 ring-1 ring-rose-500 font-semibold';
                      iconClass = 'border-rose-500 bg-rose-500 text-white';
                    } else {
                      optClass = 'border-slate-200 dark:border-surface-darkBorder opacity-50 cursor-not-allowed';
                    }
                  }

                  return (
                    <button
                      key={i}
                      disabled={isCurrentLocked || isEvaluating}
                      onClick={() => handleAnswerSubmit(currentQ.id, opt)}
                      className={`w-full flex items-center justify-between rounded-xl p-3.5 text-sm font-medium text-left border transition-all ${optClass}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-all ${iconClass}`}>
                          {String.fromCharCode(65 + i)}
                        </div>
                        <span>{opt}</span>
                      </div>

                      {isCurrentLocked && isCorrect && (
                        <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 ml-2" />
                      )}
                      {isCurrentLocked && isSelected && !isCorrect && (
                        <XCircle className="h-5 w-5 text-rose-600 shrink-0 ml-2" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* True / False Type: ONLY two buttons, True and False. Never 4 options */}
            {(qType === 'true_false' || qType === 'boolean') && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {['True', 'False'].map((tf, i) => {
                  const isSelected = currentSelected?.toLowerCase().startsWith(tf.toLowerCase());
                  const isCorrect = currentEval?.correct_answer?.toLowerCase().startsWith(tf.toLowerCase());

                  let optClass = 'border-slate-200 dark:border-surface-darkBorder bg-slate-50/40 dark:bg-slate-900/40 text-slate-800 dark:text-slate-200 hover:border-primary-400 hover:bg-primary-50/20';
                  let iconClass = 'border-slate-300 text-slate-400';

                  if (isCurrentLocked) {
                    if (isCorrect) {
                      optClass = 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-100 ring-1 ring-emerald-500 font-semibold';
                      iconClass = 'border-emerald-500 bg-emerald-500 text-white';
                    } else if (isSelected && !isCorrect) {
                      optClass = 'border-rose-500 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-100 ring-1 ring-rose-500 font-semibold';
                      iconClass = 'border-rose-500 bg-rose-500 text-white';
                    } else {
                      optClass = 'border-slate-200 dark:border-surface-darkBorder opacity-50 cursor-not-allowed';
                    }
                  }

                  return (
                    <button
                      key={i}
                      disabled={isCurrentLocked || isEvaluating}
                      onClick={() => handleAnswerSubmit(currentQ.id, tf)}
                      className={`flex items-center justify-center gap-3 rounded-xl p-6 text-base font-bold border transition-all ${optClass}`}
                    >
                      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-all ${iconClass}`}>
                        {tf[0]}
                      </div>
                      <span>{tf}</span>
                      {isCurrentLocked && isCorrect && (
                        <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 ml-1" />
                      )}
                      {isCurrentLocked && isSelected && !isCorrect && (
                        <XCircle className="h-5 w-5 text-rose-600 shrink-0 ml-1" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Fill-in-the-blank Type: NO options at all. Text input + Check answer */}
            {(qType === 'fill_blank' || qType === 'fill_in_blank') && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <input
                    type="text"
                    disabled={isCurrentLocked || isEvaluating}
                    value={textInputs[currentQ?.id] || ''}
                    onChange={(e) => setTextInputs((prev) => ({ ...prev, [currentQ.id]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !isCurrentLocked) {
                        handleAnswerSubmit(currentQ.id, textInputs[currentQ.id]);
                      }
                    }}
                    placeholder="Type the exact missing term..."
                    className={`flex-1 rounded-xl border px-4 py-3 text-sm focus:outline-none transition-all ${
                      isCurrentLocked
                        ? currentEval?.is_correct
                          ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-900 font-bold'
                          : 'border-rose-500 bg-rose-50 dark:bg-rose-950/20 text-rose-900 font-bold'
                        : 'border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard text-slate-900 dark:text-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500'
                    }`}
                  />
                  {!isCurrentLocked && (
                    <button
                      onClick={() => handleAnswerSubmit(currentQ.id, textInputs[currentQ?.id])}
                      disabled={!textInputs[currentQ?.id]?.trim() || isEvaluating}
                      className="rounded-xl bg-primary-600 px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-primary-700 disabled:opacity-40 transition-all shrink-0"
                    >
                      {isEvaluating ? 'Evaluating...' : 'Check Answer'}
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-slate-400">
                  Tip: Press <kbd className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-[10px]">Enter</kbd> to submit. Spelling tolerance and synonyms accepted.
                </p>
              </div>
            )}

            {/* Short Answer / Long Answer Type: Textarea + Submit Answer */}
            {['short_answer', 'long_answer', 'conceptual', 'application'].includes(qType) && (
              <div className="space-y-4">
                <textarea
                  rows={4}
                  disabled={isCurrentLocked || isEvaluating}
                  value={textInputs[currentQ?.id] || ''}
                  onChange={(e) => setTextInputs((prev) => ({ ...prev, [currentQ.id]: e.target.value }))}
                  placeholder="Formulate your complete answer, key definitions, and explanation..."
                  className={`w-full rounded-xl border p-4 text-sm focus:outline-none transition-all ${
                    isCurrentLocked
                      ? currentEval?.is_correct
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/20 text-slate-900 dark:text-white'
                        : 'border-amber-500 bg-amber-50 dark:bg-amber-950/20 text-slate-900 dark:text-white'
                      : 'border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard text-slate-900 dark:text-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500'
                  }`}
                />
                {!isCurrentLocked && (
                  <button
                    onClick={() => handleAnswerSubmit(currentQ.id, textInputs[currentQ?.id])}
                    disabled={!textInputs[currentQ?.id]?.trim() || isEvaluating}
                    className="rounded-xl bg-primary-600 px-6 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-primary-700 disabled:opacity-40 transition-all"
                  >
                    {isEvaluating ? 'Grading with NLP...' : 'Submit Answer for Grading'}
                  </button>
                )}
              </div>
            )}

            {/* Immediate Feedback & Explanation Callout */}
            {isCurrentLocked && (
              <div className={`mt-6 rounded-xl p-5 border text-sm leading-relaxed transition-all duration-300 space-y-3 ${
                currentEval?.is_correct
                  ? 'border-emerald-200 bg-emerald-50/70 dark:border-emerald-900/50 dark:bg-emerald-950/30 text-emerald-950 dark:text-emerald-200'
                  : 'border-rose-200 bg-rose-50/70 dark:border-rose-900/50 dark:bg-rose-950/30 text-rose-950 dark:text-rose-200'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold">
                    {currentEval?.is_correct ? (
                      <>
                        <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                        <span>Correct Answer!</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="h-5 w-5 text-rose-600" />
                        <span>Incorrect — Expected: {currentEval?.correct_answer || currentQ?.correct_answer}</span>
                      </>
                    )}
                  </div>
                  {currentEval?.score !== undefined && (
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-white/70 dark:bg-black/30 border border-current">
                      Score: {Math.round((currentEval?.score || 0) * 100)}%
                    </span>
                  )}
                </div>

                {currentEval?.feedback && (
                  <div className="text-xs bg-white/60 dark:bg-black/20 p-2.5 rounded-lg border border-current/10">
                    <span className="font-semibold">Evaluation Feedback: </span>
                    <span>{currentEval.feedback}</span>
                  </div>
                )}

                {currentEval?.key_points_covered && currentEval.key_points_covered.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="font-semibold text-emerald-800 dark:text-emerald-300">Concepts Covered:</span>
                    {currentEval.key_points_covered.map((kp, idx) => (
                      <span key={idx} className="rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200 px-2 py-0.5 font-mono text-[10px]">
                        ✓ {kp}
                      </span>
                    ))}
                  </div>
                )}

                {currentEval?.key_points_missed && currentEval.key_points_missed.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="font-semibold text-amber-800 dark:text-amber-300">Missed Points:</span>
                    {currentEval.key_points_missed.map((kp, idx) => (
                      <span key={idx} className="rounded bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 px-2 py-0.5 font-mono text-[10px]">
                        ✗ {kp}
                      </span>
                    ))}
                  </div>
                )}

                <div className="text-xs leading-relaxed text-slate-700 dark:text-slate-300 pt-1 border-t border-current/10">
                  <strong className="text-slate-900 dark:text-white">Explanation: </strong>
                  {currentEval?.explanation || currentQ?.explanation || 'Directly grounded in source concepts.'}
                  {currentEval?.source_page && (
                    <span className="ml-2 font-mono font-bold text-primary-600 dark:text-primary-400">
                      [Source: Page {currentEval.source_page}]
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-6 mt-6 border-t border-slate-100 dark:border-surface-darkBorder">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-600 dark:text-slate-400">
              <input
                type="checkbox"
                checked={markedForReview.has(currentQ?.id)}
                onChange={toggleMarkForReview}
                className="h-4 w-4 rounded border-slate-300 text-amber-500 focus:ring-amber-400"
              />
              <Bookmark className="h-4 w-4 text-amber-500" />
              <span>Mark for Review</span>
            </label>

            <div className="flex items-center gap-2">
              <button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex((idx) => Math.max(idx - 1, 0))}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </button>

              {currentIndex < questions.length - 1 ? (
                <button
                  disabled={!isCurrentLocked}
                  onClick={() => setCurrentIndex((idx) => Math.min(idx + 1, questions.length - 1))}
                  className="inline-flex items-center gap-1 rounded-xl bg-primary-600 px-4 py-2 text-xs font-semibold text-white hover:bg-primary-700 disabled:opacity-40 shadow-sm transition-all"
                >
                  Next Question
                  <ChevronRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  disabled={!isCurrentLocked || submitting}
                  onClick={handleSubmitQuiz}
                  className="inline-flex items-center gap-1 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-40 shadow-sm transition-colors"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {submitting ? 'Submitting...' : 'Finish & View Results'}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Authoritative Question Navigator Grid */}
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-sm text-slate-900 dark:text-white">
            Question Navigator
          </h3>

          <div className="grid grid-cols-5 gap-2">
            {questions.map((q, idx) => {
              const isCurrent = idx === currentIndex;
              const ev = evaluations[q.id];
              const isAnswered = !!locked[q.id];
              const isMarked = markedForReview.has(q.id);

              let style = 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
              if (isMarked) {
                style = 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300';
              } else if (isAnswered) {
                if (ev?.is_correct) {
                  style = 'bg-emerald-600 text-white font-bold';
                } else if (ev?.is_correct === false) {
                  style = 'bg-rose-600 text-white font-bold';
                } else {
                  style = 'bg-primary-600 text-white font-bold';
                }
              }

              if (isCurrent) {
                style += ' ring-2 ring-primary-500 ring-offset-2 dark:ring-offset-surface-darkCard font-extrabold';
              }

              return (
                <button
                  key={idx}
                  onClick={() => setCurrentIndex(idx)}
                  title={`Question ${idx + 1}: ${q.topic || 'General'}`}
                  className={`h-9 rounded-lg text-xs font-bold transition-all ${style}`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-surface-darkBorder space-y-2 text-[11px] text-slate-500 dark:text-slate-400">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-emerald-600" />
              <span>Correct Answer</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-rose-600" />
              <span>Incorrect Answer</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-amber-100 border border-amber-300" />
              <span>Marked for Review</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-slate-100 dark:bg-slate-800" />
              <span>Unanswered</span>
            </div>
          </div>

          <button
            onClick={handleSubmitQuiz}
            disabled={submitting || answeredCount === 0}
            className="w-full mt-4 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-40 shadow-sm transition-colors"
          >
            Submit Quiz Now
          </button>
        </div>
      </div>
    </div>
  );
};
