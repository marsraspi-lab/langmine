<script>
	import { markWordStatus } from './stores.svelte.js';

	let { word, onclose } = $props();

	function handleStatusChange(newStatus) {
		markWordStatus(word.word_simplified, newStatus);
		if (onclose) onclose();
	}

	const statusLabel = $derived(
		{
			known: 'Known',
			learning: 'Learning',
			ignored: 'Ignored',
			unknown: 'Unknown',
			'proper-name': 'Proper name'
		}[word.status] || word.status
	);

	const statusColor = $derived(
		{
			known: 'var(--green, #2ecc71)',
			learning: 'var(--orange, #e67e22)',
			ignored: 'var(--gray, #95a5a6)',
			unknown: 'var(--red, #e74c3c)',
			'proper-name': 'var(--gray, #95a5a6)'
		}[word.status] || 'inherit'
	);

	function handleKeydown(e) {
		if (e.key === 'Escape') onclose?.();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Overlay for click-outside-to-close -->
<button class="popover-overlay" onclick={onclose}></button>

<div class="word-popover">
	<button class="close-btn" onclick={onclose}>✕</button>

	<div class="word-header">
		<span class="word-text">{word.word_simplified}</span>
		{#if word.reading}
			<span class="word-reading">{word.reading}</span>
		{/if}
	</div>

	<div class="word-badges">
		{#if word.frequency_badge}
			<span class="badge freq">🔥 #{word.frequency_rank}</span>
		{/if}
		{#if word.hsk_level}
			<span class="badge hsk">HSK {word.hsk_level}</span>
		{/if}
	</div>

	<div class="word-definitions">
		{#if word.definition_de}
			<div class="def">DE: {word.definition_de}</div>
		{/if}
		{#if word.definition_en}
			<div class="def">EN: {word.definition_en}</div>
		{/if}
	</div>

	<div class="word-status">
		Status: <span style="color: {statusColor}">● {statusLabel}</span>
	</div>

	<div class="status-actions">
		{#each ['known', 'learning', 'ignored'] as s (s)}
			<button class="status-btn" disabled={word.status === s} onclick={() => handleStatusChange(s)}>
				Mark {s}
			</button>
		{/each}
	</div>

	<div class="sentences-section">
		<div class="sentences-title">Example sentences ({word.sentences?.length || 0}):</div>
		{#if word.sentences?.length}
			{#each word.sentences as s (s.id)}
				<div class="sentence-item">
					<div class="sentence-text">{s.text}</div>
					{#if s.reading}
						<div class="sentence-reading">{s.reading}</div>
					{/if}
					{#if s.translation}
						<div class="sentence-translation">{s.translation}</div>
					{/if}
				</div>
			{/each}
		{:else}
			<div class="no-sentences">No example sentences yet</div>
		{/if}
	</div>
</div>

<style>
	.popover-overlay {
		position: fixed;
		inset: 0;
		z-index: 90;
		background: transparent;
		border: none;
		cursor: default;
	}
	.word-popover {
		position: fixed;
		left: 50%;
		top: 50%;
		transform: translate(-50%, -50%);
		z-index: 100;
		background: var(--bg-card, #1e1e2e);
		border: 1px solid var(--border, #333);
		border-radius: 10px;
		padding: 20px 24px;
		min-width: 320px;
		max-width: 420px;
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
	}
	.close-btn {
		position: absolute;
		top: 10px;
		right: 14px;
		background: none;
		border: none;
		color: var(--text-muted, #888);
		font-size: 18px;
		cursor: pointer;
		padding: 4px 8px;
	}
	.close-btn:hover {
		color: var(--text, #eee);
	}
	.word-header {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin-bottom: 8px;
	}
	.word-text {
		font-size: 28px;
		font-weight: 600;
		color: var(--text, #eee);
	}
	.word-reading {
		font-size: 16px;
		color: var(--text-muted, #aaa);
	}
	.word-badges {
		display: flex;
		gap: 8px;
		margin-bottom: 12px;
	}
	.badge {
		font-size: 12px;
		padding: 2px 8px;
		border-radius: 4px;
		background: var(--bg-accent, #2a2a3e);
	}
	.word-definitions {
		margin-bottom: 12px;
	}
	.def {
		font-size: 14px;
		color: var(--text-muted, #bbb);
		line-height: 1.5;
	}
	.word-status {
		font-size: 14px;
		margin-bottom: 12px;
		color: var(--text-muted, #bbb);
	}
	.status-actions {
		display: flex;
		gap: 6px;
		margin-bottom: 16px;
	}
	.status-btn {
		flex: 1;
		padding: 6px 10px;
		font-size: 13px;
		border: 1px solid var(--border, #444);
		border-radius: 6px;
		background: var(--bg-card, #1e1e2e);
		color: var(--text, #eee);
		cursor: pointer;
	}
	.status-btn:hover:not(:disabled) {
		background: var(--bg-accent, #2a2a3e);
	}
	.status-btn:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.sentences-title {
		font-size: 13px;
		color: var(--text-muted, #888);
		margin-bottom: 8px;
	}
	.sentence-item {
		background: var(--bg-accent, #252535);
		border-radius: 6px;
		padding: 10px 12px;
		margin-bottom: 8px;
	}
	.sentence-text {
		font-size: 16px;
		color: var(--text, #eee);
	}
	.sentence-reading {
		font-size: 13px;
		color: var(--text-muted, #aaa);
		margin-top: 2px;
	}
	.sentence-translation {
		font-size: 13px;
		color: var(--text-muted, #999);
		margin-top: 2px;
	}
	.no-sentences {
		font-size: 13px;
		color: var(--text-muted, #666);
		font-style: italic;
	}
</style>
