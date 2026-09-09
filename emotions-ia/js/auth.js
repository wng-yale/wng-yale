/**
 * AES-256-GCM decryption for password-protected pages, plus a reusable
 * per-file decrypt-and-download helper for the shortlist PDF directory.
 * Uses Web Crypto API with PBKDF2 key derivation.
 *
 * Stores the password in sessionStorage so that navigating between
 * pages does not re-prompt. The password is cleared when the tab closes.
 *
 * IMPORTANT: the gate page's decrypt flow uses document.write() to
 * replace the ENTIRE document with the decrypted app HTML -- that
 * destroys this script's original closure/scope. So the app page
 * includes this same auth.js file again (see app_template.html), and
 * everything it needs is exposed on window.FAJCrypto rather than kept
 * private, so both pages can use it.
 */

(function() {
    'use strict';

    var SESSION_KEY = 'emotions_ia_pwd';
    var SALT_BYTES = 16;
    var IV_BYTES = 12;
    var ITERATIONS = 600000;

    /**
     * Derive an AES-256-GCM key from a password using PBKDF2.
     */
    async function deriveKey(password, salt) {
        var enc = new TextEncoder();
        var keyMaterial = await crypto.subtle.importKey(
            'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']
        );
        return crypto.subtle.deriveKey(
            { name: 'PBKDF2', salt: salt, iterations: ITERATIONS, hash: 'SHA-256' },
            keyMaterial,
            { name: 'AES-GCM', length: 256 },
            false,
            ['decrypt']
        );
    }

    /**
     * Decrypt raw bytes. Format: salt(16) || iv(12) || ciphertext.
     * Returns an ArrayBuffer of the plaintext.
     */
    async function decryptBytes(raw, password) {
        var salt = raw.slice(0, SALT_BYTES);
        var iv = raw.slice(SALT_BYTES, SALT_BYTES + IV_BYTES);
        var ciphertext = raw.slice(SALT_BYTES + IV_BYTES);
        var key = await deriveKey(password, salt);
        return crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv }, key, ciphertext);
    }

    /**
     * Decrypt the base64-encoded page payload to a UTF-8 HTML string.
     * Format: base64(salt || iv || ciphertext).
     */
    async function decryptString(encryptedB64, password) {
        var raw = Uint8Array.from(atob(encryptedB64), function(c) { return c.charCodeAt(0); });
        var plaintext = await decryptBytes(raw, password);
        return new TextDecoder().decode(plaintext);
    }

    /**
     * Fetch an encrypted file (e.g. docs/papers/<id>.pdf.enc), decrypt it
     * with the saved session password, and trigger a browser download.
     * mimeType defaults to PDF since that's this site's only current use.
     */
    async function decryptAndDownloadFile(url, filename, mimeType) {
        var password = sessionStorage.getItem(SESSION_KEY);
        if (!password) {
            alert('Session expired -- please reload and re-enter the password.');
            return;
        }
        var resp = await fetch(url);
        if (!resp.ok) {
            alert('Could not fetch ' + url + ' (' + resp.status + ')');
            return;
        }
        var raw = new Uint8Array(await resp.arrayBuffer());
        var plaintext = await decryptBytes(raw, password);
        var blob = new Blob([plaintext], { type: mimeType || 'application/pdf' });
        var objectUrl = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = objectUrl; a.download = filename;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(objectUrl); }, 1000);
    }

    window.FAJCrypto = {
        SESSION_KEY: SESSION_KEY,
        decryptString: decryptString,
        decryptAndDownloadFile: decryptAndDownloadFile,
    };

    /**
     * Replace the current page with decrypted HTML content.
     */
    function replacePage(html) {
        document.open();
        document.write(html);
        document.close();
    }

    /**
     * Try to decrypt and display the page content (gate page only --
     * no-ops harmlessly if #encrypted-payload isn't on this page, so it's
     * safe for the app page to include this same script file too).
     */
    async function tryDecrypt(password) {
        var payload = document.getElementById('encrypted-payload');
        if (!payload) return false;

        try {
            var html = await decryptString(payload.textContent.trim(), password);
            sessionStorage.setItem(SESSION_KEY, password);
            replacePage(html);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Handle form submission: decrypt and replace page content.
     */
    window.handleDecrypt = async function(event) {
        event.preventDefault();
        var password = document.getElementById('password-input').value;
        var errorMsg = document.getElementById('error-msg');

        if (!password) return false;

        var success = await tryDecrypt(password);
        if (!success) {
            errorMsg.style.display = 'block';
            document.getElementById('password-input').value = '';
            document.getElementById('password-input').focus();
        }
        return false;
    };

    /**
     * Support a password embedded in the URL fragment (#pw=...), for a
     * desktop launcher that unlocks with one click. The fragment is never
     * sent to the server (GitHub Pages never sees it, so it's not in
     * anyone's server logs) and is stripped from the visible URL/history
     * immediately via replaceState, before anything else runs.
     */
    function getPasswordFromHash() {
        var m = window.location.hash.match(/[#&]pw=([^&]+)/);
        return m ? decodeURIComponent(m[1]) : null;
    }

    var payloadEl = document.getElementById('encrypted-payload');
    if (payloadEl) {
        var hashPassword = getPasswordFromHash();
        if (hashPassword) {
            history.replaceState(null, '', window.location.pathname + window.location.search);
            tryDecrypt(hashPassword);
        } else {
            // Auto-decrypt if password is already in sessionStorage
            var savedPassword = sessionStorage.getItem(SESSION_KEY);
            if (savedPassword) tryDecrypt(savedPassword);
        }
    }
})();
