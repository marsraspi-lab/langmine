import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: '.',
	timeout: 15000,
	retries: 0,
	use: {
		baseURL: 'http://127.0.0.1:8099',
		headless: true
	},
	webServer: {
		command: 'python e2e/test_server.py',
		url: 'http://127.0.0.1:8099/api/videos',
		timeout: 10000,
		reuseExistingServer: false
	}
});
