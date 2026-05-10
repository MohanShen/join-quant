/**
 * strategy/loader.js
 * 
 * Loads and validates custom strategy files from the local filesystem.
 * 
 * Supported formats:
 *   - .py Python files (raw strategy code)
 *   - .json config files pointing to strategy + params
 * 
 * Usage:
 *   const { StrategyLoader } = require('./loader');
 *   const loader = new StrategyLoader();
 *   const strategy = await loader.load('./my-strategies/ma-cross.py');
 */

const fs = require('fs');
const path = require('path');

class StrategyLoader {
  /**
   * @param {object} options
   * @param {string} options.baseDir - Base directory for strategies (default: ./strategies)
   */
  constructor(options = {}) {
    this.baseDir = options.baseDir || path.join(process.cwd(), 'strategies');
  }

  /**
   * Load a strategy from a file path.
   * 
   * @param {string} filePath - Absolute or relative path to strategy file
   * @returns {Promise<StrategyObject>}
   */
  async load(filePath) {
    // Resolve to absolute path
    const absolutePath = path.isAbsolute(filePath)
      ? filePath
      : path.resolve(this.baseDir, filePath);

    if (!fs.existsSync(absolutePath)) {
      throw new Error(`Strategy file not found: ${absolutePath}`);
    }

    const ext = path.extname(absolutePath).toLowerCase();
    const name = path.basename(absolutePath, ext);

    if (ext === '.py') {
      return this._loadPython(absolutePath, name);
    } else if (ext === '.json') {
      return this._loadJson(absolutePath, name);
    } else {
      throw new Error(`Unsupported strategy file type: ${ext}. Use .py or .json`);
    }
  }

  /**
   * Load a Python strategy file.
   * @private
   */
  async _loadPython(filePath, name) {
    const sourceCode = fs.readFileSync(filePath, 'utf8');
    
    // Basic validation
    this._validatePython(sourceCode);

    return {
      name,
      sourceCode,
      language: 'python',
      path: filePath,
      metadata: this._extractMetadata(sourceCode)
    };
  }

  /**
   * Load a JSON config file.
   * JSON can contain:
   *   - Inline sourceCode
   *   - Reference to a .py file
   *   - Strategy params (initCash, dates, etc.)
   * 
   * @private
   */
  async _loadJson(filePath, name) {
    const content = fs.readFileSync(filePath, 'utf8');
    const config = JSON.parse(content);

    let sourceCode;
    
    if (config.sourceCode) {
      sourceCode = config.sourceCode;
    } else if (config.sourceFile) {
      // Load from referenced .py file
      const sourcePath = path.resolve(path.dirname(filePath), config.sourceFile);
      sourceCode = fs.readFileSync(sourcePath, 'utf8');
    } else {
      throw new Error(`JSON config must have either sourceCode or sourceFile field: ${filePath}`);
    }

    this._validatePython(sourceCode);

    return {
      name: config.name || name,
      sourceCode,
      language: 'python',
      path: filePath,
      metadata: {
        ...config.metadata || {},
        ...this._extractMetadata(sourceCode)
      },
      params: {
        initCash: config.initCash || 100000,
        startDate: config.startDate || null,
        endDate: config.endDate || null,
        frequency: config.frequency || 'minute',
        ...config.params
      }
    };
  }

  /**
   * Basic Python validation - check for required JoinQuant API functions.
   * @private
   */
  _validatePython(sourceCode) {
    const required = ['initialize', 'handle_data'];
    const missing = required.filter(fn => !sourceCode.includes(`def ${fn}`));
    
    if (missing.length > 0) {
      console.warn(`[loader] Strategy missing recommended functions: ${missing.join(', ')}`);
    }

    // Check for common issues
    if (sourceCode.includes('run.py') || sourceCode.includes('sys.path')) {
      console.warn('[loader] Strategy appears to have local import references that may not work in JoinQuant');
    }
  }

  /**
   * Extract metadata from strategy source comments.
   * Looks for:
   *   - Strategy name (from comment)
   *   - Author
   *   - Description
   *   - Required packages
   * 
   * @private
   */
  _extractMetadata(sourceCode) {
    const metadata = {
      packages: []
    };

    // Look for # Clone from ... comments
    const cloneMatch = sourceCode.match(/# ?Clone from [^\n]+/i);
    if (cloneMatch) {
      metadata.clonedFrom = cloneMatch[0].replace(/^# ?/i, '').trim();
    }

    // Look for pip requirements in comments
    const pipMatch = sourceCode.match(/# ?requirements[^\n]*\n([^\n]+(?:\n[^\n]+)*)/i);
    if (pipMatch) {
      const reqs = pipMatch[1].match(/[a-zA-Z0-9_-]+/g);
      if (reqs) metadata.packages = reqs;
    }

    // Look for description in docstring
    const docstringMatch = sourceCode.match(/'''[\s\S]*?'''/);
    if (docstringMatch) {
      metadata.docstring = docstringMatch[0].substring(3, docstringMatch[0].length - 3).trim().substring(0, 200);
    }

    return metadata;
  }

  /**
   * List all strategy files in the base directory.
   * 
   * @param {boolean} recursive - Include subdirectories (default: true)
   * @returns {Array<{name, path, language, size, modified}>}
   */
  list(recursive = true) {
    if (!fs.existsSync(this.baseDir)) {
      return [];
    }

    const strategies = [];
    
    const scan = (dir) => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        
        if (entry.isDirectory() && recursive) {
          scan(fullPath);
        } else if (entry.isFile()) {
          const ext = path.extname(entry.name).toLowerCase();
          if (['.py', '.json'].includes(ext)) {
            const stats = fs.statSync(fullPath);
            strategies.push({
              name: path.basename(entry.name, ext),
              path: fullPath,
              language: ext === '.py' ? 'python' : 'json',
              size: stats.size,
              modified: stats.mtime
            });
          }
        }
      }
    };

    scan(this.baseDir);
    return strategies;
  }
}

module.exports = { StrategyLoader };