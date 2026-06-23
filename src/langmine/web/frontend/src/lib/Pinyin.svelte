<script>
	// Color each pinyin syllable by tone (Pleco-style).
	// Splits on space, detects tone from diacritic marks, wraps in colored spans.

	let { text = '' } = $props();

	const TONE_MARK = {
		// tone 1: macron
		ā: 1,
		ē: 1,
		ī: 1,
		ō: 1,
		ū: 1,
		ǖ: 1,
		Ā: 1,
		Ē: 1,
		Ī: 1,
		Ō: 1,
		Ū: 1,
		Ǖ: 1,
		// tone 2: acute
		á: 2,
		é: 2,
		í: 2,
		ó: 2,
		ú: 2,
		ǘ: 2,
		Á: 2,
		É: 2,
		Í: 2,
		Ó: 2,
		Ú: 2,
		Ǘ: 2,
		// tone 3: caron
		ǎ: 3,
		ě: 3,
		ǐ: 3,
		ǒ: 3,
		ǔ: 3,
		ǚ: 3,
		Ǎ: 3,
		Ě: 3,
		Ǐ: 3,
		Ǒ: 3,
		Ǔ: 3,
		Ǚ: 3,
		// tone 4: grave
		à: 4,
		è: 4,
		ì: 4,
		ò: 4,
		ù: 4,
		ǜ: 4,
		À: 4,
		È: 4,
		Ì: 4,
		Ò: 4,
		Ù: 4,
		Ǜ: 4
	};

	const TONE_CLASS = {
		1: 'tone1',
		2: 'tone2',
		3: 'tone3',
		4: 'tone4',
		5: 'tone5'
	};

	function getTone(syllable) {
		for (const char of syllable) {
			if (TONE_MARK[char]) return TONE_MARK[char];
		}
		return 5; // neutral
	}

	let syllables = $derived(text ? text.split(/\s+/) : []);
</script>

{#if syllables.length > 0}
	{#each syllables as syl, idx (idx)}
		{#if idx > 0}

		{/if}
		<span class={TONE_CLASS[getTone(syl)]}>{syl}</span>
	{/each}
{/if}

<style>
	.tone1 {
		color: #e74c3c;
	} /* red — high level */
	.tone2 {
		color: #2ecc71;
	} /* green — rising */
	.tone3 {
		color: #3498db;
	} /* blue — dipping */
	.tone4 {
		color: #9b59b6;
	} /* purple — falling */
	.tone5 {
		color: #95a5a6;
	} /* gray — neutral */
</style>
