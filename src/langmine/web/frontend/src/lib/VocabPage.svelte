<script>
	import { fetchSubtlexVocab } from './api.js';
	import WordPopover from './WordPopover.svelte';
	import Pinyin from './Pinyin.svelte';
	import { app } from './stores.svelte.js';

	let words = $state([]);
	let total = $state(0);
	let page = $state(1);
	let perPage = $state(100);
	let statusFilter = $state(null);
	let searchQuery = $state('');
	let counts = $state({ all: 0, known: 0, learning: 0, ignored: 0, unknown: 0 });
	let loading = $state(false);
	let error = $state(null);
	let selectedWord = $state(null);

	// Debounce search
	let searchTimer = null;

	async function loadWords() {
		loading = true;
		error = null;
		try {
			const data = await fetchSubtlexVocab(page, perPage, statusFilter, searchQuery || null);
			words = data.words;
			total = data.total;
			counts = data.counts;
		} catch (err) {
			error = err.message;
			words = [];
		} finally {
			loading = false;
		}
	}

	function handleSearchInput(e) {
		searchQuery = e.target.value;
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			page = 1;
			loadWords();
		}, 300);
	}

	function goToPage(p) {
		if (p < 1 || p > totalPages || p === page) return;
		page = p;
		selectedWord = null;
		loadWords();
	}

	function setFilter(f) {
		if (statusFilter === f) return;
		statusFilter = f;
		page = 1;
		selectedWord = null;
		loadWords();
	}

	function handlePageKeydown(e) {
		if (e.key === 'Enter') {
			const p = parseInt(e.target.value);
			if (p >= 1) goToPage(p);
		}
	}

	// Read cross-view search query on mount
	if (app.vocabSearchQuery) {
		searchQuery = app.vocabSearchQuery;
		app.vocabSearchQuery = '';
	}

	// Load on mount
	$effect(() => {
		loadWords();
	});

	let totalPages = $derived(Math.ceil(total / perPage));

	const statuses = [
		{ key: null, label: 'All', countKey: 'all' },
		{ key: 'known', label: 'Known', countKey: 'known' },
		{ key: 'learning', label: 'Learning', countKey: 'learning' },
		{ key: 'ignored', label: 'Ignored', countKey: 'ignored' },
		{ key: 'unknown', label: 'Unknown', countKey: 'unknown' }
	];

	function statusClass(s) {
		return (
			{ known: 's-known', learning: 's-learning', ignored: 's-ignored', unknown: 's-unknown' }[s] ||
			''
		);
	}

	function openPopover(word) {
		selectedWord = word;
	}

	function closePopover() {
		selectedWord = null;
	}

	function handleReclassified() {
		// If the word no longer matches the filter, splice it out
		if (statusFilter && selectedWord) {
			if (selectedWord.status !== statusFilter) {
				const idx = words.findIndex((w) => w.word_simplified === selectedWord.word_simplified);
				if (idx >= 0) {
					const oldStatus = statusFilter;
					const newStatus = selectedWord.status;
					counts = {
						...counts,
						[oldStatus]: Math.max(0, (counts[oldStatus] || 0) - 1),
						[newStatus]: (counts[newStatus] || 0) + 1
					};
					words.splice(idx, 1);
				}
			}
		}
		closePopover();
	}
</script>

<div class="vocab-page">
	<!-- Filter tabs -->
	<div class="filter-tabs">
		{#each statuses as st (st.key)}
			<button
				class="filter-tab"
				class:active={statusFilter === st.key}
				onclick={() => setFilter(st.key)}
			>
				{st.label}
				{counts[st.countKey]?.toLocaleString()}
			</button>
		{/each}
	</div>

	<!-- Search -->
	<div class="search-bar">
		<input
			type="text"
			placeholder="Search words..."
			value={searchQuery}
			oninput={handleSearchInput}
		/>
	</div>

	<!-- Content -->
	{#if loading}
		<div class="loading">Loading...</div>
	{:else if error}
		<div class="error">
			{error}
			<button onclick={loadWords}>Retry</button>
		</div>
	{:else if words.length === 0}
		<div class="empty">No words found</div>
	{:else}
		<div class="word-list">
			<div class="list-header">
				<span class="col-rank">#</span>
				<span class="col-word">Word</span>
				<span class="col-reading">Reading</span>
				<span class="col-freq">Freq</span>
				<span class="col-status">Status</span>
			</div>
			{#each words as word (word.word_simplified)}
				<button class="word-row" onclick={() => openPopover(word)}>
					<span class="col-rank">{word.frequency_rank}</span>
					<span class="col-word">{word.word_simplified}</span>
					<span class="col-reading"><Pinyin text={word.reading} /></span>
					<span class="col-freq">{word.frequency_badge}#{word.frequency_rank}</span>
					<span class="col-status {statusClass(word.status)}">● {word.status}</span>
				</button>
			{/each}
		</div>

		<!-- Pagination -->
		<div class="pagination">
			<button onclick={() => goToPage(1)} disabled={page === 1}>◀◀ First</button>
			<button onclick={() => goToPage(page - 1)} disabled={page === 1}>◀ Prev</button>
			<span class="page-info">
				Page
				<input
					type="number"
					class="page-input"
					value={page}
					min="1"
					max={totalPages}
					onkeydown={handlePageKeydown}
				/>
				of {totalPages.toLocaleString()}
			</span>
			<button onclick={() => goToPage(page + 1)} disabled={page === totalPages}>Next ▶</button>
			<button onclick={() => goToPage(totalPages)} disabled={page === totalPages}>Last ▶▶</button>
		</div>
	{/if}
</div>

<!-- Popover -->
{#if selectedWord}
	<WordPopover word={selectedWord} onclose={handleReclassified} />
{/if}

<style>
	.vocab-page {
		padding: 20px;
		max-width: 900px;
		margin: 0 auto;
		color: var(--text, #eee);
	}
	.filter-tabs {
		display: flex;
		gap: 4px;
		margin-bottom: 16px;
		flex-wrap: wrap;
	}
	.filter-tab {
		padding: 6px 14px;
		border: 1px solid var(--border, #444);
		border-radius: 6px;
		background: var(--bg-card, #1e1e2e);
		color: var(--text, #eee);
		cursor: pointer;
		font-size: 13px;
	}
	.filter-tab:hover {
		background: var(--bg-accent, #2a2a3e);
	}
	.filter-tab.active {
		background: var(--accent, #5a7aff);
		border-color: var(--accent, #5a7aff);
		color: white;
	}
	.search-bar input {
		width: 100%;
		padding: 8px 14px;
		border: 1px solid var(--border, #444);
		border-radius: 6px;
		background: var(--bg-card, #1e1e2e);
		color: var(--text, #eee);
		font-size: 14px;
		margin-bottom: 16px;
		box-sizing: border-box;
	}
	.word-list {
		margin-bottom: 16px;
	}
	.list-header {
		display: flex;
		padding: 8px 0;
		border-bottom: 2px solid var(--border, #444);
		font-size: 12px;
		font-weight: 600;
		color: var(--text-muted, #888);
		text-transform: uppercase;
	}
	.word-row {
		display: flex;
		align-items: center;
		padding: 8px 0;
		border-bottom: 1px solid var(--border-faint, #2a2a3e);
		cursor: pointer;
		background: none;
		border-left: none;
		border-right: none;
		width: 100%;
		text-align: left;
		color: var(--text, #eee);
		font-size: 14px;
	}
	.word-row:hover {
		background: var(--bg-accent, #252535);
	}
	.col-rank {
		width: 60px;
		font-size: 12px;
		color: var(--text-muted, #888);
	}
	.col-word {
		width: 120px;
		font-weight: 600;
		font-size: 16px;
	}
	.col-reading {
		flex: 1;
		color: var(--text-muted, #aaa);
	}
	.col-freq {
		width: 100px;
		font-size: 12px;
	}
	.col-status {
		width: 100px;
		font-size: 12px;
	}
	.s-known {
		color: var(--green, #2ecc71);
	}
	.s-learning {
		color: var(--orange, #e67e22);
	}
	.s-ignored {
		color: var(--gray, #95a5a6);
	}
	.s-unknown {
		color: var(--red, #e74c3c);
	}
	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
	}
	.pagination button {
		padding: 6px 12px;
		border: 1px solid var(--border, #444);
		border-radius: 6px;
		background: var(--bg-card, #1e1e2e);
		color: var(--text, #eee);
		cursor: pointer;
		font-size: 13px;
	}
	.pagination button:hover:not(:disabled) {
		background: var(--bg-accent, #2a2a3e);
	}
	.pagination button:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.page-info {
		font-size: 13px;
		color: var(--text-muted, #aaa);
	}
	.page-input {
		width: 50px;
		padding: 4px 8px;
		border: 1px solid var(--border, #444);
		border-radius: 4px;
		background: var(--bg-card, #1e1e2e);
		color: var(--text, #eee);
		text-align: center;
		font-size: 13px;
	}
	.loading,
	.error,
	.empty {
		text-align: center;
		padding: 60px 20px;
		color: var(--text-muted, #888);
	}
	.error button {
		margin-left: 10px;
		padding: 4px 12px;
		cursor: pointer;
	}
</style>
