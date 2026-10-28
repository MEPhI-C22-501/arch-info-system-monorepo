import { renderToStaticMarkup } from 'react-dom/server';
import { expect, test } from 'vitest';
import { AttachmentFrame } from './AttachmentFrame';

test('attachment preview isolates active content from the application', () => {
  const html = renderToStaticMarkup(<AttachmentFrame name="uploaded.html" url="blob:attachment"/>);
  expect(html).toContain('sandbox=""');
  expect(html).not.toContain('allow-scripts');
  expect(html).not.toContain('allow-same-origin');
  expect(html).toContain('src="blob:attachment"');
});
