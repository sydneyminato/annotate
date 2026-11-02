#include <stdint.h>

#define NIL 0
#define ATOM_COND 1
#define ATOM_LAMBDA 2
#define ATOM_TRUE 3

typedef uint32_t cell_t; // 4バイトの極小コンスセル（上位16bit: CAR, 下位16bit: CDR）

// 引き算ハッシュ：記号をその瞬間に極小の数値へと削ぎ落とす回路
uint8_t annotate_hash(const char* str) {
    uint8_t hash = 0;
    while (*str) {
        hash = (hash << 4) ^ (*str++); // ビットシフトとXORのみ
    }
    return hash & 0x3F; // OBLISTサイズ（63）のマスクで住所を強制収束
}

// 外部からカーネルロジックを呼び出すためのプロトタイプ宣言
cell_t car(cell_t cell);
cell_t cdr(cell_t cell);
cell_t cons(cell_t car_val, cell_t cdr_val);
cell_t lookup_env(cell_t symbol, cell_t env);
int is_symbol(cell_t exp);
int is_atom(cell_t exp);

// EVAL: 過去の記憶に頼らず、「今、ここ」の文脈(env)だけで式を評価する循環ループ
cell_t eval(cell_t exp, cell_t env) {
    if (is_symbol(exp)) {
        return lookup_env(exp, env);
    }
    if (is_atom(exp)) {
        return exp;
    }

    cell_t func = car(exp);
    cell_t args = cdr(exp);

    // COND (条件分岐): その場の摩擦（条件）だけで道を切り拓く
    if (func == ATOM_COND) {
        while (args != NIL) {
            cell_t clause = car(args);
            if (eval(car(clause), env) != NIL) {
                return eval(car(cdr(clause)), env);
            }
            args = cdr(args);
        }
        return NIL;
    }

    // LAMBDA (関数の生成): その場で新しい道具を創発する
    if (func == ATOM_LAMBDA) {
        return cons(exp, env); // 現在の文脈をアノテートした閉包を返す
    }

    return NIL;
}