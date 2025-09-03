const isspace = (c: string) => c === ' ' || c === '\t' || c === '\n' || c === '\r';
const isalpha = (c: string) => 'a' <= c.toLowerCase() && c.toLowerCase() <= 'z';
const isdigit = (c: string) => '0' <= c && c <= '9';
const isalnum = (c: string) => isalpha(c) || isdigit(c);

interface Token {
  location: number;
  length: number;
  kind: string;
}

function token_to_string(token: Token, s: string): string {
  return s.slice(token.location, token.location + token.length);
}

function token_at(s: string, p: number): Token {
  while (true) {
    while (p < s.length && isspace(s[p])) p += 1;
    if (p + 1 < s.length && s[p] === '/' && s[p + 1] == '/') {
      while (p < s.length && s[p] != '\n') p += 1;
      continue;
    }
    break;
  }
  if (p >= s.length) return {location: p, length: 0, kind: "END_OF_INPUT"};
  const start = p;
  if (isalpha(s[p]) || s[p] == '_') {
    while (p < s.length && (isalnum(s[p]) || s[p] == '_')) p += 1;
    return {location: start, length: p - start, kind: "IDENTIFIER"};
  }
  if (isdigit(s[p])) {
    while (p < s.length && isdigit(s[p])) p += 1;
    return {location: start, length: p - start, kind: "NUMBER"};
  }
  switch (s[p]) {
    case '+': case '-': case '*': case '/': case ':': case '=':
    case '.': case ',': case ';': case '(': case ')': case '{':
    case '}': case '#': case '%': case '^':
      return {location: start, length: 1, kind: s[p]};
    default:
      return {location: start, length: 1, kind: "ERROR"};
  }
}

interface Module {
  kind: "MODULE";
  children: Array<Expr | Stmt>
}

interface Block {
  kind: "BLOCK";
  children: Array<Expr | Stmt>;
}

interface Procedure {
  kind: "PROCEDURE";
  identifier: Token;
  parameters: Declaration[];
  return_type: Expr;
  attributes: Declaration[];
  body: Block;
}

interface Declaration {
  kind: "DECLARATION";
  identifier: Token;
  typespec: Expr | null;
  expression: Expr | null;
}

interface NumberExpr {
  kind: "NUMBEREXPR";
  token: Token;
}

interface EnumLiteral {
  kind: "ENUMLITERAL";
  token: Token;
}

interface Variable {
  kind: "VARIABLE";
  token: Token;
}

interface Call {
  kind: "CALL";
  expression: Expr;
  args: Array<Expr | Declaration>;
}

interface BinaryOp {
  kind: "BINARYOP";
  lhs: Expr;
  op: Token;
  rhs: Expr;
}

type Expr = NumberExpr | EnumLiteral | Variable | Call | BinaryOp;
type Stmt = Block | Procedure | Declaration;

class Parser {
  s: string;
  p: number;

  constructor(s: string) {
    this.s = s;
    this.p = 0;
  }

  peek(n: number = 1): Token {
    if (n <= 0) throw new Error();
    let token: Token;
    let p = this.p;
    for (let i = 0; i < n; i += 1) {
      token = token_at(this.s, p);
      p = token.location + token.length;
    }
    return token!;
  }

  eat(expect: string): Token {
    const token = token_at(this.s, this.p);
    if (expect !== token.kind) throw new Error(`expected ${expect}, got ${token.kind}`);
    this.p = token.location + token.length;
    return token;
  }

  parse_Declaration(): Declaration {
    const identifier = this.eat("IDENTIFIER");
    let typespec: Expr | null = null;
    if (this.peek().kind === ':') {
      this.eat(':')
      typespec = this.parse_Expr();
    }
    let expression: Expr | null = null;
    if (this.peek().kind === '=') {
      this.eat('=');
      expression = this.parse_Expr();
    }
    if (typespec === null && expression === null) throw new Error();
    return {kind: "DECLARATION", identifier, typespec, expression};
  }

  parse_Procedure(): Procedure {
    const identifier = this.eat("IDENTIFIER");
    this.eat('=');
    this.eat('(');
    const parameters: Declaration[] = [];
    while (this.peek().kind !== ')') {
      parameters.push(this.parse_Declaration());
      if (this.peek().kind === ',') this.eat(',');
      else break;
    }
    this.eat(')');
    const return_type = this.parse_Expr();
    const attributes: Declaration[] = [];
    if (this.peek().kind === '#') {
      this.eat('#');
      this.eat(')');
      while (this.peek().kind !== ')') {
        attributes.push(this.parse_Declaration());
        if (this.peek().kind === ',') this.eat(',');
        else break;
      }
      this.eat(')');
    }
    const body = this.parse_Block();
    return {kind: "PROCEDURE", identifier, parameters, return_type, attributes, body};
  }

  parse_Block(): Block {
    this.eat('{');
    const children: Array<Expr | Stmt> = [];
    while (this.peek().kind !== '}') {
      children.push(this.parse_Expr_or_Stmt());
    }
    this.eat('}');
    return {kind: "BLOCK", children};
  }

  parse_Stmt(): Stmt {
    if (this.peek(2).kind === "=" && this.peek(3).kind === '(' && (this.peek(4).kind === ')' || this.peek(5).kind === ':' || this.peek(5).kind === '=')) return this.parse_Procedure();
    if (this.peek(2).kind === ':' || this.peek(2).kind === '=') return this.parse_Declaration();
    throw new Error(`not implemented ${this.peek().kind}`);
  }

  parse_factor(): Expr {
    let result: Expr | null = null;
    if (this.peek().kind === "IDENTIFIER") {
      const token = this.eat("IDENTIFIER");
      result = {kind: "VARIABLE", token};
    }
    else if (this.peek().kind === '.') {
      this.eat('.');
      const token = this.eat("IDENTIFIER");
      result = {kind: "ENUMLITERAL", token};
    } else if (this.peek().kind === "NUMBER") {
      const token = this.eat("NUMBER");
      result = {kind: "NUMBEREXPR", token};
    }
    if (result === null) throw new Error(`not implemented '${this.peek().kind}'`);
    if (this.peek().kind === '(') {
      this.eat('(');
      const args: Array<Expr | Declaration> = [];
      while (this.peek().kind !== ')') {
        if (this.peek(2).kind === '=') args.push(this.parse_Declaration());
        else args.push(this.parse_Expr());
        if (this.peek().kind === ',') this.eat(',');
        else break;
      }
      this.eat(')');
      result = {kind: "CALL", expression: result, args};
    }
    return result!;
  }

  parse_term(): Expr {
    let result = this.parse_factor()
    while (this.peek().kind === '*' || this.peek().kind === '/' || this.peek().kind === '%') {
      const op = this.eat(this.peek().kind);
      const rhs = this.parse_factor();
      result = {kind: "BINARYOP", lhs: result, op, rhs};
    }
    return result;
  }

  parse_Expr(): Expr {
    let result = this.parse_term()
    while (this.peek().kind === '+' || this.peek().kind === '-') {
      const op = this.eat(this.peek().kind);
      const rhs = this.parse_term();
      result = {kind: "BINARYOP", lhs: result, op, rhs};
    }
    return result;
  }

  parse_Expr_or_Stmt(): Expr | Stmt {
    if (this.peek(2).kind === ':' || this.peek(2).kind === '=') return this.parse_Stmt();
    else return this.parse_Expr();
  }

  parse_Module(): Module {
    const children: Array<Expr | Stmt> = [];
    while (this.peek().kind !== "END_OF_INPUT") {
      children.push(this.parse_Expr_or_Stmt());
    }
    return {kind: "MODULE", children};
  }
}

function printVisit(node: Module | Stmt | Expr, s: string): string {
  switch (node.kind) {
    case "MODULE":
      return node.children.map(child => printVisit(child, s)).join("\n");
    case "DECLARATION": {
      let result = `${token_to_string(node.identifier, s)}`;
      if (node.typespec) result += `: ${printVisit(node.typespec, s)}`
      if (node.expression) result += ` = ${printVisit(node.expression, s)}`
      return result;
    }
    case "PROCEDURE": {
      let result = `${token_to_string(node.identifier, s)} = `;
      result += `(${node.parameters.map(parameter => printVisit(parameter, s)).join(", ")}) `;
      result += `${printVisit(node.return_type, s)} `;
      if (node.attributes.length !== 0) result += `#(${node.attributes.map(attribute => printVisit(attribute, s)).join(", ")}) `;
      result += printVisit(node.body, s);
      return result;
    }
    case "BLOCK": {
      let result = `{\n`;
      result += `${node.children.map(child => printVisit(child, s)).join("\n")}`;
      result += `\n}`;
      return result;
    }
    case "BINARYOP":
      return `${printVisit(node.lhs, s)} ${token_to_string(node.op, s)} ${printVisit(node.rhs, s)}`;
    case "CALL":
      return `${printVisit(node.expression, s)}(${node.args.map(arg => printVisit(arg, s)).join(", ")})`;
    case "VARIABLE":
      return `${token_to_string(node.token, s)}`;
    case "ENUMLITERAL":
      return `.${token_to_string(node.token, s)}`;
    case "NUMBEREXPR":
      return `${token_to_string(node.token, s)}`;
    default:
      throw new Error(node);
  }
}

(async () => {
  if (Bun.argv.length < 3) {
    console.error("usage:", Bun.argv[0], Bun.argv[1], "file.aperion");
    process.exit(1);
  }
  const file = Bun.file(Bun.argv[2]);
  const src = await file.text();

  const parser = new Parser(src);
  const module = parser.parse_Module();
  console.log(printVisit(module, parser.s));
})();
