import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Layers,
  Sparkles,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  AlertCircle,
  HelpCircle,
  Filter,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { flashcardsApi } from '../api/flashcards';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';

export const Flashcards = () => {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get('documentId') || '';

  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(initialDocId);
  const [flashcards, setFlashcards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [filterDifficult, setFilterDifficult] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await documentsApi.list();
        setDocuments(res.items || []);
        if (!selectedDocId && (res.items || []).length > 0) {
          setSelectedDocId(res.items[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchDocs();
  }, []);

  const loadCards = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      const cards = await flashcardsApi.list(selectedDocId);
      setFlashcards(cards || []);
      setCurrentIndex(0);
      setIsFlipped(false);
    } catch (e) {
      console.error('Failed to load flashcards:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCards();
  }, [selectedDocId]);

  const handleGenerate = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      await flashcardsApi.generate(selectedDocId);
      await loadCards();
    } catch (e) {
      alert('Failed to generate flashcards: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMarkDifficulty = async (difficulty) => {
    const card = displayCards[currentIndex];
    if (!card) return;
    try {
      await flashcardsApi.review(card.id, difficulty);
      // Advance to next card
      if (currentIndex < displayCards.length - 1) {
        setCurrentIndex((i) => i + 1);
        setIsFlipped(false);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const displayCards = filterDifficult
    ? flashcards.filter((c) => c.difficulty_mark === 'difficult')
    : flashcards;

  const currentCard = displayCards[currentIndex];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Flashcards Study Deck
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Reinforce core definitions and exam concepts through active recall and spaced repetition.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            className="rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-xs font-semibold text-slate-800 dark:text-white focus:outline-none"
          >
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.original_filename}
              </option>
            ))}
          </select>

          <button
            onClick={handleGenerate}
            disabled={loading || !selectedDocId}
            className="inline-flex items-center gap-1.5 rounded-xl bg-primary-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Generate Deck</span>
          </button>
        </div>
      </div>

      {/* Filter and Deck Stats Bar */}
      <div className="flex items-center justify-between bg-white dark:bg-surface-darkCard p-4 rounded-xl border border-slate-200 dark:border-surface-darkBorder text-xs">
        <div className="flex items-center gap-4">
          <span className="font-semibold text-slate-600 dark:text-slate-300">
            Deck: {displayCards.length} cards
          </span>
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-600 dark:text-slate-400">
            <input
              type="checkbox"
              checked={filterDifficult}
              onChange={(e) => {
                setFilterDifficult(e.target.checked);
                setCurrentIndex(0);
                setIsFlipped(false);
              }}
              className="rounded border-slate-300 text-primary-600"
            />
            <span>Difficult Only</span>
          </label>
        </div>

        {displayCards.length > 0 && (
          <span className="font-mono text-slate-400">
            Card {currentIndex + 1} of {displayCards.length}
          </span>
        )}
      </div>

      {/* Main Flashcard Container with Flip Interaction */}
      {displayCards.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No flashcards in deck"
          description="Click 'Generate Deck' to synthesize flashcards from document definitions and key terms."
          actionLabel="Generate Now"
          onAction={handleGenerate}
        />
      ) : (
        <div className="space-y-6">
          <div
            onClick={() => setIsFlipped(!isFlipped)}
            className="cursor-pointer min-h-[300px] rounded-2xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-8 shadow-sm flex flex-col justify-between hover:shadow-md transition-all text-center"
          >
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="uppercase tracking-wider font-semibold">
                {isFlipped ? 'Definition / Answer' : 'Term / Concept'}
              </span>
              <span className="flex items-center gap-1 text-primary-600 dark:text-primary-400 font-medium">
                <RotateCw className="h-3 w-3" />
                Click to flip
              </span>
            </div>

            <div className="my-auto py-6">
              {!isFlipped ? (
                <h2 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white max-w-md mx-auto leading-relaxed">
                  {currentCard?.front}
                </h2>
              ) : (
                <div className="space-y-3">
                  <p className="text-base text-slate-800 dark:text-slate-200 max-w-lg mx-auto leading-relaxed font-normal">
                    {currentCard?.back}
                  </p>
                  {currentCard?.source_page && (
                    <span className="inline-block font-mono text-xs text-primary-600 dark:text-primary-400 font-bold">
                      [Page {currentCard.source_page}]
                    </span>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-center text-xs text-slate-400">
              <span>{currentCard?.topic || 'General Topic'}</span>
            </div>
          </div>

          {/* Difficulty Rating Buttons (When Flipped) */}
          {isFlipped && (
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => handleMarkDifficulty('easy')}
                className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-xs font-bold text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300 transition-colors"
              >
                Easy (Review Later)
              </button>
              <button
                onClick={() => handleMarkDifficulty('medium')}
                className="rounded-xl border border-blue-300 bg-blue-50 px-4 py-2 text-xs font-bold text-blue-700 hover:bg-blue-100 dark:bg-blue-950/40 dark:text-blue-300 transition-colors"
              >
                Medium
              </button>
              <button
                onClick={() => handleMarkDifficulty('difficult')}
                className="rounded-xl border border-red-300 bg-red-50 px-4 py-2 text-xs font-bold text-red-700 hover:bg-red-100 dark:bg-red-950/40 dark:text-red-300 transition-colors"
              >
                Difficult (Review Soon)
              </button>
            </div>
          )}

          {/* Navigation Controls */}
          <div className="flex items-center justify-between pt-2">
            <button
              disabled={currentIndex === 0}
              onClick={() => {
                setCurrentIndex((i) => Math.max(i - 1, 0));
                setIsFlipped(false);
              }}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous Card
            </button>

            <button
              disabled={currentIndex >= displayCards.length - 1}
              onClick={() => {
                setCurrentIndex((i) => Math.min(i + 1, displayCards.length - 1));
                setIsFlipped(false);
              }}
              className="inline-flex items-center gap-1 rounded-xl bg-primary-600 px-4 py-2 text-xs font-semibold text-white hover:bg-primary-700 disabled:opacity-40"
            >
              Next Card
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
