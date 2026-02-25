
export const renderMessageContent = (content: any, message_type?: string, isDM?: boolean) => {
    try {
        if (!content) return "";
        if (typeof content !== 'string') return String(content);

        // ONLY parse JSON if explicitly marked as narration/rich_text or it's from the DM (legacy fallback)
        const shouldParseJson = message_type === 'narration' || message_type === 'rich_text' || (!message_type && isDM);

        if (shouldParseJson) {
            const trimmed = content.trim();
            if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
                (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
                try {
                    const parsed = JSON.parse(trimmed);

                    // 2. Handle Arrays (Rich Text)
                    if (Array.isArray(parsed)) {
                        return parsed.map((block: any, i: number) => {
                            if (typeof block === 'string') return <span key={i}>{block}</span>;
                            if (block?.type === 'text') return <span key={i}>{block.text}</span>;
                            return null;
                        });
                    }

                    // 3. Handle Single Object
                    if (typeof parsed === 'object' && parsed !== null) {
                        return parsed.text || JSON.stringify(parsed);
                    }

                    return String(parsed);
                } catch {
                    // Not JSON, fall through
                }
            }
        }

        // Default: Plain Text
        return content;

    } catch (e) {
        console.error("Error rendering message:", e);
        return String(content);
    }
};

export const applyCommandSuggestion = (inputValue: string, selectedText: string, isArgument: boolean): string => {
    if (isArgument) {
        const parts = inputValue.trimStart().split(' ');
        const baseCmd = parts[0];

        const lowerInput = inputValue.toLowerCase();
        const lowerSel = selectedText.toLowerCase();

        let suffixLen = 0;
        for (let i = 1; i <= Math.min(lowerInput.length, lowerSel.length); i++) {
            if (lowerInput.endsWith(lowerSel.substring(0, i))) {
                suffixLen = i;
            }
        }

        if (suffixLen > 0) {
            return inputValue.substring(0, inputValue.length - suffixLen) + selectedText + ' ';
        } else {
            const lastSpace = inputValue.lastIndexOf(' ');
            if (lastSpace !== -1) {
                return inputValue.substring(0, lastSpace + 1) + selectedText + ' ';
            } else {
                return `${baseCmd} ${selectedText} `;
            }
        }
    } else {
        return `@${selectedText} `;
    }
};
