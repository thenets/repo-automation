/**
 * Logger utility for hierarchical, indented logging
 * Provides structured console output with proper indentation
 */
class Logger {
  constructor() {
    this.indentLevel = 0;
    this.indentStr = '  ';
  }

  /**
   * Get current indentation prefix
   */
  getPrefix() {
    return this.indentStr.repeat(this.indentLevel);
  }

  /**
   * Log a message with current indentation
   */
  log(message) {
    console.log(this.getPrefix() + message);
  }

  /**
   * Log an info message (alias for log)
   */
  info(message) {
    this.log(message);
  }

  /**
   * Log an error message with current indentation
   */
  error(message) {
    console.error(this.getPrefix() + message);
  }

  /**
   * Log a success message with current indentation
   */
  success(message) {
    this.log(message);
  }

  /**
   * Log a warning message with current indentation
   */
  warn(message) {
    console.warn(this.getPrefix() + message);
  }

  /**
   * Increase indentation level
   */
  indent() {
    this.indentLevel++;
  }

  /**
   * Decrease indentation level
   */
  outdent() {
    if (this.indentLevel > 0) {
      this.indentLevel--;
    }
  }

  /**
   * Execute a function with increased indentation
   * Automatically handles indent/outdent
   */
  async group(title, asyncFn) {
    if (title) {
      this.log(title);
    }
    this.indent();
    try {
      const result = await asyncFn();
      this.outdent();
      return result;
    } catch (error) {
      this.outdent();
      throw error;
    }
  }

  /**
   * Execute a synchronous function with increased indentation
   */
  groupSync(title, fn) {
    if (title) {
      this.log(title);
    }
    this.indent();
    try {
      const result = fn();
      this.outdent();
      return result;
    } catch (error) {
      this.outdent();
      throw error;
    }
  }

  /**
   * Reset indentation to zero
   */
  reset() {
    this.indentLevel = 0;
  }

  /**
   * Get current indentation level
   */
  getIndentLevel() {
    return this.indentLevel;
  }
}

// Create a singleton instance
const logger = new Logger();

module.exports = { Logger, logger };