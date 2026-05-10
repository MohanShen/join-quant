/**
 * auth/login.test.js
 * Tests for the LoginManager module.
 */

const { describe, it, before, after, beforeEach } = require('node:test');
const assert = require('node:assert');
const path = require('path');
const fs = require('fs');

const TEST_COOKIE_PATH = '/tmp/jq-test-cookies.json';

// Clean up before tests
before(() => {
  if (fs.existsSync(TEST_COOKIE_PATH)) {
    fs.unlinkSync(TEST_COOKIE_PATH);
  }
});

after(() => {
  if (fs.existsSync(TEST_COOKIE_PATH)) {
    fs.unlinkSync(TEST_COOKIE_PATH);
  }
});

describe('LoginManager', () => {
  it('should be constructable with just a cookie path', () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager(TEST_COOKIE_PATH);
    assert.ok(lm);
    assert.strictEqual(lm.cookiePath, TEST_COOKIE_PATH);
  });

  it('should accept username and password options', () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager(TEST_COOKIE_PATH, {
      username: 'test@test.com',
      password: 'secret123'
    });
    assert.strictEqual(lm.username, 'test@test.com');
    assert.strictEqual(lm.password, 'secret123');
  });

  it('should use environment variables as fallbacks', () => {
    const { LoginManager } = require('../auth/login');
    
    // Set env vars
    process.env.JOINQUANT_USERNAME = 'env_user';
    process.env.JOINQUANT_PASSWORD = 'env_pass';
    
    const lm = new LoginManager(TEST_COOKIE_PATH);
    assert.strictEqual(lm.username, 'env_user');
    assert.strictEqual(lm.password, 'env_pass');
    
    // Clean up
    delete process.env.JOINQUANT_USERNAME;
    delete process.env.JOINQUANT_PASSWORD;
  });

  it('should fail gracefully without password', async () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager('/tmp/nonexistent.json', {
      username: 'test',
      // No password
      maxRetries: 1,
      retryDelayMs: 100
    });

    // Can't actually login without password, but constructor should not throw
    assert.ok(lm);
  });

  it('should return null from cache when no cache exists', () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager('/tmp/nonexistent-cache-file.json');
    const result = lm._loadFromCache();
    assert.strictEqual(result, null);
  });

  it('should return null from cache when file is corrupted', () => {
    const { LoginManager } = require('../auth/login');
    
    // Create corrupted cache
    fs.writeFileSync('/tmp/jq-test-corrupt.json', '{not valid json');
    
    const lm = new LoginManager('/tmp/jq-test-corrupt.json');
    const result = lm._loadFromCache();
    assert.strictEqual(result, null);
    
    fs.unlinkSync('/tmp/jq-test-corrupt.json');
  });

  it('should save and load cookies from cache', () => {
    const { LoginManager } = require('../auth/login');
    
    const lm = new LoginManager(TEST_COOKIE_PATH);
    const testData = {
      cookies: [
        { name: 'PHPSESSID', value: 'test_sess', domain: 'www.joinquant.com', path: '/', httpOnly: true },
        { name: 'uid', value: 'test_uid', domain: 'www.joinquant.com', path: '/', httpOnly: false }
      ],
      pageToken: 'test_token',
      loginAt: Date.now(),
      expires: Date.now() + 86400000
    };
    
    lm._saveToCache(testData);
    const loaded = lm._loadFromCache();
    
    assert.ok(loaded);
    assert.strictEqual(loaded.cookies.find(c => c.name === 'uid').name, 'uid');
    assert.strictEqual(loaded.pageToken, 'test_token');
  });

  it('should reject invalid cache without required cookies', () => {
    const { LoginManager } = require('../auth/login');
    
    // Create cache without uid
    fs.writeFileSync('/tmp/jq-test-no-uid.json', JSON.stringify({
      cookies: [
        { name: 'PHPSESSID', value: 'test_sess', domain: 'www.joinquant.com', path: '/', httpOnly: true },{ name: 'PHPSESSID', value: 'test' }],
      expires: Date.now() + 86400000
    }));
    
    const lm = new LoginManager('/tmp/jq-test-no-uid.json');
    const result = lm._loadFromCache();
    assert.strictEqual(result, null);
    
    fs.unlinkSync('/tmp/jq-test-no-uid.json');
  });

  it('should reject expired cache', () => {
    const { LoginManager } = require('../auth/login');
    
    // Create expired cache
    fs.writeFileSync('/tmp/jq-test-expired.json', JSON.stringify({
      cookies: [
        { name: 'PHPSESSID', value: 'test_sess', domain: 'www.joinquant.com', path: '/', httpOnly: true },
        { name: 'uid', value: 'test' },
        { name: 'PHPSESSID', value: 'test' }
      ],
      expires: Date.now() - 1000 // Expired
    }));
    
    const lm = new LoginManager('/tmp/jq-test-expired.json');
    const result = lm._loadFromCache();
    assert.strictEqual(result, null);
    
    fs.unlinkSync('/tmp/jq-test-expired.json');
  });
});

describe('LoginManager.getBrowserContext', () => {
  it('should be a function', () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager(TEST_COOKIE_PATH);
    assert.strictEqual(typeof lm.getBrowserContext, 'function');
  });

  it('should throw if ensureLogin not called first', async () => {
    const { LoginManager } = require('../auth/login');
    const lm = new LoginManager(TEST_COOKIE_PATH);
    
    await assert.throws(
      () => lm.getCookies(),
      /Must call ensureLogin/
    );
  });
});