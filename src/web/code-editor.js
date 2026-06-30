// the codemirror library does not provide esm exports,
// so we manually bundled them using vite and host it from s3.
//   gross... i know.

import * as SC from 'https://nyc3.digitaloceanspaces.com/drain/hawk/1745077162763.mjs'
import { LitElement, html, css } from 'https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js';
import { feather } from '/web/feather.js';

const hoonParser = {
  startState() {
    return {indented: 0};
  },
  token(stream, state) {
    if (stream.sol()) {
      state.indented = stream.indentation();
    }
    
    if (stream.match("::")) {
      stream.skipToEnd();
      return "comment";
    }
    stream.next();
    return null;
  },
  blankLine(state) {},
  indent(state) {
    return state.indented;
  }
};

const hoonFolding = SC.foldService.of((state, pos) => {
  const startLine = state.doc.lineAt(pos);
  const baseIndent = /^\s*/.exec(startLine.text)?.[0].length ?? 0;

  const lastLine = state.doc.lines;
  let endLineNumber = startLine.number;

  const maxLine = state.doc.lines;
  if (startLine.number == maxLine) return null;
  
  // Peek at the next line
  const nextLine = state.doc.line(startLine.number + 1);
  const nextLineIndent = /^\s*/.exec(nextLine.text)?.[0].length ?? 0;

  if (
    startLine.number === lastLine || // no next line
    nextLine.text.trim() === "" ||
    !(nextLine.text.trimStart() === "::") ||
    nextLineIndent <= baseIndent
  ) {
    return null;
  }

  for (let i = startLine.number + 1; i <= lastLine; i++) {
    const line = state.doc.line(i);
    if (line.text.trim() === "") continue;

    const indent = /^\s*/.exec(line.text)?.[0].length ?? 0;
    if (indent <= baseIndent) break;

    endLineNumber = i;
  }

  const endLine = state.doc.line(endLineNumber);
  return {from: startLine.to, to: endLine.to};
})

const hoonLanguage = SC.StreamLanguage.define(hoonParser);


const featherHighlight = SC.HighlightStyle.define([
  {tag: SC.t.comment, class: "cm-comment"},
]);

function hoon() {
  return new SC.LanguageSupport(hoonLanguage, [
    hoonFolding,
    hoonLanguage.data.of({
      commentTokens: { line: "::" },
    }),
  ]);
}

class SpineCodeEditor extends LitElement {

  static properties = {
    mite: { type: String },  // language
    settings: { type: Boolean },
    vim: { type: Boolean },
    wrap: { type: Boolean },
    pairMatching: { type: Boolean },
    lineNumbers: { type: Boolean },
  };
  
  get toggles() {
    return {
      vim: false,
      wrap: false,
      pairMatching: true,
      lineNumbers: true,
    }
  }

  constructor() {
    super();
    this.mite = '/text/plain'
    this.editor = undefined;
  }

  connectedCallback() {
    super.connectedCallback()
    this.addEventListener('focus', () => this.editor?.focus());
  }
  
  save() {
    this.closest('form').requestSubmit();
  }
  foldAll() {
    let cm = this.editor?.cm?.cm6;
    if (cm) {
      SC.foldAll(cm)
    }
  }
  
  saveSettings() {
    let settings = Object.entries(this.toggles).map(([k,v]) => {
      return [k, this[k]]
    })
    localStorage.setItem(
      'spine-code-editor-settings',
      JSON.stringify(Object.fromEntries(settings))
    )
  }
  
  loadSettings() {
    let localSettings = {}
    try {
      localSettings = JSON.parse(
        localStorage.getItem('spine-code-editor-settings')
      )
    } catch (e) { }

    Object.entries({
      ...this.toggles,
      ...localSettings,
    }).forEach(([k,v]) => {
      this[k] = v;
    })
  }

  firstUpdated () {
    this.loadSettings();
    
    const parent = this.renderRoot.querySelector('.editor')
    
    SC.Vim.defineEx('write', 'w', (e, d, k) => {
      let that = e?.cm6.dom?.getRootNode().host;
      that?.save()
    });

    SC.Vim.mapCommand("s", "action", "toggle-fold")
    SC.Vim.defineAction("toggle-fold", (e) => {
      let cm = e?.cm6
      const line = cm.state.doc.lineAt(cm.state.selection.main.head);
      SC.toggleFold(cm, line.from)
    });
    SC.Vim.mapCommand("S", "action", "fold-all")
    SC.Vim.defineAction("fold-all", (e) => {
      let cm = e?.cm6
      SC.foldAll(cm)
    });
    SC.Vim.mapCommand("ZZ", "action", "save-and-close")
    SC.Vim.defineAction("save-and-close", (e) => {
      let that = e?.cm6.dom?.getRootNode().host;
      that?.save()
      if (globalThis.closeTabs) {
        globalThis.closeTabs()
      }
    });

    this.editor = new SC.EditorView({
      extensions: this.exts,
      root: this.shadowRoot,
      parent
    })
    
    const form = this.closest('form');
    const name = this.getAttribute('name');
    if (form && !!name) {
      form.addEventListener('formdata', (e) => {
        e.formData.append(name, this.value);
      });
    }

    this.loadTextFromNodes(Array.from(this.childNodes));
  }

  updated(changedProperties) {
    this.editor.setState(
      SC.EditorState.create({
        doc: this.editor.state.doc,
        extensions: this.exts,
      })
    )
  }

  get spineKeymap() {
    return [
      {
        key: "Ctrl-s",
        preventDefault: true,
        run: () => {
          this.save();
          return true;
        }
      },
      {
        key: "Meta-s",
        preventDefault: true,
        run: () => {
          this.save();
          return true;
        }
      },
      {
        key: "Tab",
        preventDefault: true,
        run: SC.commands.indentMore,
      },
      {
        key: "Shift-Tab",
        preventDefault: true,
        run: SC.commands.indentLess,
      },
    ];
  }

  get exts() {
    let base = [
      SC.history(),
      SC.drawSelection(),
      SC.dropCursor(),
      SC.EditorState.allowMultipleSelections.of(true),
      SC.indentOnInput(),
      SC.rectangularSelection(),
      SC.crosshairCursor(),
      SC.highlightSelectionMatches(),
      SC.bracketMatching(),
      SC.syntaxHighlighting(featherHighlight),
      SC.search({top: true}),
      SC.keymap.of([
        ...this.spineKeymap,
        ...SC.closeBracketsKeymap,
        ...SC.defaultKeymap,
        ...SC.searchKeymap,
        ...SC.historyKeymap,
        ...SC.foldKeymap,
      ])
    ];
    return [
      ...(this.vim ? [SC.vim()] : []),
      ...base,
      ...(this.wrap ? [SC.EditorView.lineWrapping] : []),
      ...(this.lineNumbers ? [
          SC.lineNumbers(),
          SC.foldGutter(),
          SC.highlightActiveLineGutter(),
        ] : []),
      ...(this.pairMatching ? [
          SC.closeBrackets(),
        ] : []),
      ...((this.mite.startsWith('/text/hawk') ||
           this.mite.startsWith('/text/hoon')) ?
           [hoon()] : []
         ),
      ...(this.mite.includes('javascript') ?
           [SC.javascript()] : []
         ),
    ];
  }
  
  get value() {
    const parent = this.renderRoot.querySelector('.editor')
    return this.editor.state.doc.toString();
  }

  static styles = [feather,
    css`
      :host {
        overflow: hidden;
        white-space: normal !important;
        box-shadow: unset !important;
      }
      .cm-editor {
        background-color: unset;
        color: var(--f0);
        flex-grow: 1;
        overflow: auto;
        outline: none;
        box-shadow: unset !important;
      }
      .cm-editor.cm-focused {
        box-shadow: unset !important;
      }
      .cm-editor .cm-gutters {
        color: var(--f1);
        background-color: var(--b1);
        border-right: 0.5px solid var(--b4);
      }
      .cm-editor .cm-linenumber {
        color: var(--f2);
        background-color: var(--b1);
        opacity: 0.5;
      }
      .cm-editor .cm-foldmarker {
        margin-left: 10px;
        opacity: 65%;
      }
      .cm-editor .cm-activeLine {
        background-color: unset;
      }
      .cm-editor .cm-selectionBackground {
        background-color: var(--b3);
      }
      .cm-editor .cm-activeLineGutter {
        color: var(--b0);
        background-color: var(--f3);
      }
      .cm-editor.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground {
        background-color: var(--b4) !important;
      }
      .cm-editor .cm-keyword {
        color: var(--f1);
      }
      .cm-editor .cm-string {
        color: var(--f1);
      }
      .cm-editor .cm-comment {
        color: var(--f4);
      }
      .cm-editor .cm-content {
        color: var(--f0);
        box-shadow: unset !important;
      }
      .cm-editor .cm-scroller {
        box-shadow: unset !important;
        padding-bottom: 250px;
      }
      .cm-editor .cm-cursor {
        border-left: 2px solid var(--f-1);
      }
      .cm-editor .cm-fat-cursor {
        background-color: var(--b-1);
      }
      .cm-editor:not(.cm-focsed) .cm-fat-cursor {
        outline: var(--f-1) solid 1px;
      }
    `,
  ]

  toggle(key) {
    return html`
      <label class="fc g1 js ac">
        <span>${key}</span>
        <input
          type="checkbox"
          ?checked="${this[key]}"
          @input="${(e) => this[key] = e.target.checked}"
        />
      </label>
    `
  }

  render () {
    return html`
      <div class="wf hf fc scroll-none p0 no-outline">
        <div class="bd1 mono p0 no-outline">
          <div class="b1 frw je no-outline">
            <button
              class="p-1 hover b1 ${this.settings ? 'toggled' : ''}"
              @click="${() => this.settings = !this.settings}"
              >settings
            </button>
            <button
              class="p-1 hover b1"
              @click="${() => SC.openSearchPanel(this.editor)}"
              >search
            </button>
          </div>
          <div class="p3 no-outline frw g4 b0 ${this.settings ? '' : 'hidden'}">
            ${Object.keys(this.toggles).map(t => this.toggle(t))}
            <div
              class="p1 basis-full">
              <span class="f4">
                settings are immediately applied.<br/>
                to also apply in future sessions:
              </span>
              <button
                class="br1 bd1 b1 hover p-1"
                @click="${this.saveSettings}"
              >save config</button>
            </div>
          </div>
        </div>
        <div class="editor grow scroll-none p0 fc no-outline"></div>
      </div>
      <slot class="hidden" @slotchange="${this.handleSlotchange}"></slot>
    `
  }
  
  loadTextFromNodes(childNodes) {
    if (!this.editor) return;
    let text = childNodes.map((node) => {
      return node.textContent ? node.textContent : ''
    }).join('');
    const transaction = this.editor.state.update({
      changes: {
        from: 0,
        to: this.editor.state.doc.length,
        insert: text
      },
    });
    this.editor.dispatch(transaction);
  }

  handleSlotchange(e) {
    this.loadTextFromNodes(e.target.assignedNodes({flatten: true}));
  }
}

customElements.define('spine-code-editor', SpineCodeEditor)
