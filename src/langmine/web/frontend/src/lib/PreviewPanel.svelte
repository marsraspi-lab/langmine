<script>
	let { data } = $props();

	let collapsed = $state(false);
</script>

{#if data}
	<div class="preview-panel" class:collapsed>
		<button class="preview-toggle" onclick={() => (collapsed = !collapsed)}>
			<span class="toggle-icon">{collapsed ? '▶' : '▼'}</span>
			<span class="toggle-label">Difficulty Preview</span>
			{#if !collapsed}
				<span
					class="toggle-dismiss"
					onclick={(e) => {
						e.stopPropagation();
						data = null;
					}}
					role="button"
					tabindex="0"
					onkeydown={(e) => {
						if (e.key === 'Enter') data = null;
					}}>✕</span
				>
			{/if}
		</button>

		{#if !collapsed}
			<div class="preview-stats">
				<div class="stat">
					<span class="stat-value">{data.total_sentences}</span>
					<span class="stat-label">sentences</span>
				</div>
				<div class="stat">
					<span class="stat-value">{data.i1_estimated}</span>
					<span class="stat-label">🔥 i+1</span>
				</div>
				<div class="stat">
					<span class="stat-value">{data.i0_count}</span>
					<span class="stat-label">✅ known</span>
				</div>
				<div class="stat">
					<span class="stat-value">{data.stash_count}</span>
					<span class="stat-label">📦 stashed</span>
				</div>
				<div class="stat">
					<span class="stat-value">{data.known_word_pct}%</span>
					<span class="stat-label">known words</span>
				</div>
				<div class="stat">
					<span class="stat-value">{data.avg_unknown_per_sentence}</span>
					<span class="stat-label">avg unknowns/sentence</span>
				</div>
			</div>

			<div class="preview-transcript">
				{#each data.sentences as sentence, idx (idx)}
					<div class="preview-sentence">
						<span class="sentence-idx">{idx + 1}.</span>
						<span class="sentence-words">
							{#each sentence.words as word, widx (word.token + widx)}
								<span class="word-token word-{word.status}">{word.token}</span>
							{/each}
						</span>
						{#if sentence.reading}
							<div class="sentence-reading">{sentence.reading}</div>
						{/if}
						{#if sentence.translation_de}
							<div class="sentence-translation">{sentence.translation_de}</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.preview-panel {
		border-bottom: 1px solid var(--border);
	}
	.preview-toggle {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 20px;
		border: none;
		background: rgba(255, 255, 255, 0.03);
		color: var(--text);
		cursor: pointer;
		font-size: 0.85rem;
		text-align: left;
	}
	.preview-toggle:hover {
		background: rgba(255, 255, 255, 0.06);
	}
	.toggle-icon {
		font-size: 0.6rem;
		color: var(--text-secondary);
		width: 12px;
	}
	.toggle-label {
		flex: 1;
		font-weight: 600;
	}
	.toggle-dismiss {
		color: var(--text-secondary);
		font-size: 0.8rem;
		padding: 2px 6px;
		border-radius: 3px;
	}
	.toggle-dismiss:hover {
		color: var(--accent);
		background: rgba(233, 69, 96, 0.1);
	}
	.preview-stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
		padding: 8px 20px 12px;
	}
	.stat {
		text-align: center;
		padding: 6px 4px;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 6px;
	}
	.stat-value {
		display: block;
		font-size: 1rem;
		font-weight: 700;
		color: var(--accent);
	}
	.stat-label {
		display: block;
		font-size: 0.65rem;
		color: var(--text-secondary);
		margin-top: 2px;
	}
	.preview-transcript {
		padding: 0 20px 12px;
		max-height: 300px;
		overflow-y: auto;
		font-size: 0.8rem;
		line-height: 1.6;
	}
	.preview-sentence {
		margin-bottom: 10px;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.05);
	}
	.sentence-idx {
		color: var(--text-secondary);
		margin-right: 6px;
		font-size: 0.7rem;
		vertical-align: top;
	}
	.sentence-words {
		display: inline;
	}
	.word-token {
		padding: 1px 2px;
		border-radius: 2px;
	}
	.word-known {
		color: var(--accent-green);
	}
	.word-learning {
		color: var(--accent);
		font-weight: 600;
		border-bottom: 1.5px solid var(--accent);
	}
	.word-non-word {
		color: var(--text-secondary);
		opacity: 0.6;
	}
	.sentence-reading {
		color: var(--text-secondary);
		font-size: 0.75rem;
		margin-top: 2px;
	}
	.sentence-translation {
		color: var(--text-secondary);
		font-size: 0.75rem;
		font-style: italic;
	}
</style>
