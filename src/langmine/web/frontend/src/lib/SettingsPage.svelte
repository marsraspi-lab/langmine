<script>
  import { config, saveConfig } from './stores.js';

  let saving = $state(false);

  async function handleSave(e) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    const updates = {};
    for (const [key, val] of data.entries()) {
      updates[key] = val;
    }
    // Convert numeric fields
    const numericFields = [
      'sentence_gap_ms', 'audio_pad_before_ms', 'audio_pad_after_ms',
      'max_cards_per_video', 'max_stash_cards', 'hsk_bootstrap',
    ];
    for (const field of numericFields) {
      if (updates[field] !== undefined) {
        updates[field] = parseInt(updates[field], 10);
      }
    }
    saving = true;
    try {
      await saveConfig(updates);
    } finally {
      saving = false;
    }
  }
</script>

<div class="settings-page">
  <h2>⚙️ Settings</h2>

  <form onsubmit={handleSave}>
    <section class="settings-section">
      <h3>Anki</h3>
      <label>
        Connect URL
        <input name="anki_connect_url" value={$config.anki_connect_url || ''} />
      </label>
      <label>
        Deck Name
        <input name="deck_name" value={$config.deck_name || ''} />
      </label>
      <label>
        Note Type
        <input name="note_type" value={$config.note_type || ''} />
      </label>
    </section>

    <section class="settings-section">
      <h3>Language</h3>
      <label>
        Source Language
        <input name="source_language" value={$config.source_language || ''} maxlength="6" />
      </label>
      <label>
        Target Language
        <input name="target_language" value={$config.target_language || ''} maxlength="6" />
      </label>
      <label>
        Translation API
        <select name="translation_api">
          <option value="google" selected={$config.translation_api === 'google'}>Google Translate</option>
          <option value="deepl" selected={$config.translation_api === 'deepl'}>DeepL</option>
        </select>
      </label>
    </section>

    <section class="settings-section">
      <h3>Mining</h3>
      <label>
        Sentence Gap (ms)
        <input name="sentence_gap_ms" type="number" value={$config.sentence_gap_ms || 500} min="0" max="5000" />
      </label>
      <label>
        Audio Pad Before (ms)
        <input name="audio_pad_before_ms" type="number" value={$config.audio_pad_before_ms || 250} min="0" max="2000" />
      </label>
      <label>
        Audio Pad After (ms)
        <input name="audio_pad_after_ms" type="number" value={$config.audio_pad_after_ms || 300} min="0" max="2000" />
      </label>
      <label>
        Max Cards Per Video
        <input name="max_cards_per_video" type="number" value={$config.max_cards_per_video || 20} min="1" max="100" />
      </label>
      <label>
        Max Stash Cards
        <input name="max_stash_cards" type="number" value={$config.max_stash_cards || 20} min="1" max="100" />
      </label>
    </section>

    <section class="settings-section">
      <h3>Vocabulary</h3>
      <label>
        HSK Bootstrap Level
        <input name="hsk_bootstrap" type="number" value={$config.hsk_bootstrap || 3} min="1" max="6" />
      </label>
    </section>

    <button type="submit" class="save-btn" disabled={saving}>
      {saving ? '⏳ Saving...' : '💾 Save Settings'}
    </button>
  </form>
</div>

<style>
  .settings-page {
    max-width: 640px;
  }
  h2 {
    margin-bottom: 24px;
    color: var(--text);
  }
  .settings-section {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
  }
  h3 {
    margin: 0 0 16px 0;
    font-size: 1rem;
    color: var(--accent);
  }
  label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    color: var(--text-secondary);
    font-size: 0.9rem;
    gap: 12px;
  }
  label:last-child {
    margin-bottom: 0;
  }
  input, select {
    width: 240px;
    padding: 6px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-size: 0.9rem;
    font-family: inherit;
  }
  input:focus, select:focus {
    outline: none;
    border-color: var(--accent);
  }
  .save-btn {
    padding: 10px 24px;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: var(--radius);
    font-size: 0.95rem;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .save-btn:hover {
    opacity: 0.9;
  }
  .save-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
