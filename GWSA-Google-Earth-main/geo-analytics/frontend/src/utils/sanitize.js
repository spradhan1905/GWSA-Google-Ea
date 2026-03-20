/**
 * GWSA GeoAnalytics — XSS Sanitizer
 * Wraps DOMPurify to sanitize AI responses before rendering.
 */
import DOMPurify from 'dompurify';

export const sanitizeHtml = (dirty) =>
  DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'br', 'p', 'ul', 'ol', 'li', 'code', 'pre'],
    ALLOWED_ATTR: [],
  });
