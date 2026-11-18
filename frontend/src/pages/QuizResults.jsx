import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Award,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  RotateCcw,
  BookOpen,
  Sparkles,
} from 'lucide-react';
import { quizApi } from '../api/quiz';
import { Badge } from '../components/common/Badge';

export const QuizResults = () => {
  const { id } = useParams();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      try {
        const data = await quizApi.getResults(id);
        setResults(data);
      } catch (err) {
        console.error('Failed to load quiz results:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  const scorePercent = Math.round(results?.accuracy ?? 0);
  const isPassing = scorePercent >= 60;

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Authoritative Score Ring Banner */}
      <div className="rounded-2xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-8 shadow-sm flex flex-col md:flex-row items-center justify-between gap-8">
        <div className="flex items-center gap-6">
          {/* Circular Score Gauge */}
          <div className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-8 border-primary-100 dark:border-primary-950/60">
            <div
              className={`absolute inset-0 rounded-full border-8 ${
                isPassing ? 'border-primary-600' : 'border-amber-500'
              } border-t-transparent -rotate-45`}
            />
            <div className="text-center">
              <span className="text-2xl font-extrabold text-slate-900 dark:text-white">
                {scorePercent}%
              </span>
              <span className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                Score
              </span>
            </div>
          </div>

          <div>
            <Badge variant={isPassing ? 'success' : 'warning'}>
              {isPassing ? 'Quiz Passed ✓' : 'Review Recommended'}
            </Badge>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mt-2">
              Performance Summary
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              You answered {results?.score ?? 0} out of {results?.total ?? 0} questions correctly.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Link
            to={`/quizzes/${results?.quiz_id}`}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-4 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50"
          >
            <RotateCcw className="h-4 w-4" />
            Retake Quiz
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-primary-700"
          >
            Dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
          <p className="text-xs text-slate-400 font-semibold uppercase">Total Questions</p>
          <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">{results?.total ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
          <p className="text-xs text-slate-400 font-semibold uppercase">Correct Answers</p>
          <p className="text-xl font-bold text-emerald-600 mt-1">{results?.score ?? 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
          <p className="text-xs text-slate-400 font-semibold uppercase">Incorrect</p>
          <p className="text-xl font-bold text-red-500 mt-1">{(results?.total || 0) - (results?.score || 0)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
          <p className="text-xs text-slate-400 font-semibold uppercase">Time Taken</p>
          <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">{results?.time_taken_seconds ?? 0}s</p>
        </div>
      </div>

      {/* Recommendations Box */}
      {results?.recommendations && results.recommendations.length > 0 && (
        <div className="rounded-xl border border-amber-200/80 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 p-6 shadow-sm">
          <h2 className="text-sm font-bold text-amber-900 dark:text-amber-200 mb-2 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-600" />
            Targeted Learning Recommendations
          </h2>
          <div className="space-y-2 text-xs text-amber-800 dark:text-amber-300">
            {results.recommendations.map((rec, i) => (
              <div key={i} className="flex items-center justify-between">
                <span>• {rec.topic}: Accuracy below 60%</span>
                <Link
                  to={`/questions?topic=${encodeURIComponent(rec.topic)}`}
                  className="rounded-lg bg-amber-200/60 dark:bg-amber-900/50 px-2.5 py-1 font-bold text-amber-900 dark:text-amber-200 hover:bg-amber-300/60"
                >
                  Practice Topic
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-Question Detailed Review */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">
          Detailed Question Review
        </h2>

        {(results?.responses || []).map((resp, idx) => (
          <div
            key={idx}
            className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-3"
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-400">Question {idx + 1}</span>
              {resp.is_correct ? (
                <Badge variant="success">Correct ✓</Badge>
              ) : (
                <Badge variant="danger">Incorrect ✗</Badge>
              )}
            </div>

            <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-relaxed">
              {resp.question_text}
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
              <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 p-3 border border-slate-200/50 dark:border-surface-darkBorder">
                <span className="block text-slate-400 font-semibold mb-1">Your Selection:</span>
                <span className={`font-bold ${resp.is_correct ? 'text-emerald-600' : 'text-red-500'}`}>
                  {resp.selected_answer || 'No answer selected'}
                </span>
              </div>

              <div className="rounded-lg bg-emerald-50/50 dark:bg-emerald-950/20 p-3 border border-emerald-200/50 dark:border-emerald-900/40">
                <span className="block text-emerald-800 dark:text-emerald-300 font-semibold mb-1">
                  Correct Answer:
                </span>
                <span className="font-bold text-emerald-700 dark:text-emerald-400">
                  {resp.correct_answer}
                </span>
              </div>
            </div>

            {/* Explanation & Source Citation */}
            {resp.explanation && (
              <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-600 dark:text-slate-300 border-l-2 border-primary-600">
                <span className="font-bold text-primary-700 dark:text-primary-400">Explanation: </span>
                <span>{resp.explanation}</span>
                {resp.source_page && (
                  <span className="text-primary-600 font-mono font-bold ml-2">
                    [Source: Page {resp.source_page}]
                  </span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
