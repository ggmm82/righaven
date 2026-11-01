import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import { useI18n } from "@/core/i18n/hooks";

/**
 * Hook to determine if the chat is in a specific mode based on URL parameters, and to set an initial prompt input value accordingly.
 * `?mode=skill` prefills the skill creation prompt; `?recipe=ID` prefills the recipe's starter message in the user's language.
 */
export function useSpecificChatMode() {
  const { t, locale } = useI18n();
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const searchParams = useSearchParams();
  const promptInputController = usePromptInputController();
  const recipe = threadIdFromPath === "new" ? searchParams.get("recipe") : null;
  const [recipeStarter, setRecipeStarter] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (!recipe || !/^[a-z][a-z0-9-]{1,39}$/.test(recipe)) return;
    let live = true;
    const language = locale === "it-IT" ? "it" : "en";
    void fetch(`${getBackendBaseURL()}/api/harness/recipes/${encodeURIComponent(recipe)}?locale=${language}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((v: { starter?: string } | null) => {
        if (live && v?.starter) setRecipeStarter(v.starter);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [recipe, locale]);
  const inputInitialValue = useMemo(() => {
    if (threadIdFromPath !== "new") {
      return undefined;
    }
    if (recipe) {
      return recipeStarter;
    }
    if (searchParams.get("mode") !== "skill") {
      return undefined;
    }
    return t.inputBox.createSkillPrompt;
  }, [threadIdFromPath, searchParams, recipe, recipeStarter, t.inputBox.createSkillPrompt]);
  const lastInitialValueRef = useRef<string | undefined>(undefined);
  const setInputRef = useRef(promptInputController.textInput.setInput);
  setInputRef.current = promptInputController.textInput.setInput;
  useEffect(() => {
    if (
      inputInitialValue &&
      inputInitialValue !== lastInitialValueRef.current
    ) {
      lastInitialValueRef.current = inputInitialValue;
      setTimeout(() => {
        setInputRef.current(inputInitialValue);
        const textarea = document.querySelector("textarea");
        if (textarea) {
          textarea.focus();
          textarea.selectionStart = textarea.value.length;
          textarea.selectionEnd = textarea.value.length;
        }
      }, 100);
    }
  }, [inputInitialValue]);
}
