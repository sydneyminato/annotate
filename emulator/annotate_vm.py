import sys

class AnnotateVM:
    def __init__(self):
        self.RAM_SIZE = 32768  # 32KB
        self.SECTOR_SIZE = 512
        self.VFDD_SIZE = 1440 * 1024  # 1.44MB
        
        # 物理インフラのシミュレーション（ゼロベース）
        self.ram = bytearray(self.RAM_SIZE)
        self.vfdd = bytearray(self.VFDD_SIZE)
        
        # 自由セル空間の初期化 (20KB分、約5000セル)
        self.HEAP_START = 12288  # 12KB以降
        self.HEAP_SIZE = 5000
        self.cells = [{"car": 0, "cdr": 0, "marked": False} for _ in range(self.HEAP_SIZE)]
        self.free_list = 1
        
        # 空きセルを繋ぐ（フリーリストの初期化）
        for i in range(1, self.HEAP_SIZE - 1):
            self.cells[i]["cdr"] = i + 1

    def prim_fdd_write(self, sector_num, data_list):
        """仮想FDDのセクタにリスト構造をアノテート(書き込み)する原子命令"""
        offset = sector_num * self.SECTOR_SIZE
        if offset + self.SECTOR_SIZE > self.VFDD_SIZE:
            return 0
        # ダミーのバイナリ化として4バイトずつパッキング
        for i, val in enumerate(data_list[:128]):
            self.vfdd[offset + i*4 : offset + i*4 + 4] = int(val).to_bytes(4, 'big')
        return 1

    def prim_fdd_read(self, sector_num):
        """仮想FDDからデータを読み込み、LISPのリストとして想起する原子命令"""
        offset = sector_num * self.SECTOR_SIZE
        result = []
        for i in range(128):
            val = int.from_bytes(self.vfdd[offset + i*4 : offset + i*4 + 4], 'big')
            if val != 0:
                result.append(val)
        return result

    def garbage_collect(self, root_env):
        """マーク＆スイープによる、過去の記憶の徹底的な忘却と更地化"""
        # 1. MARK
        def mark(idx):
            if idx == 0 or idx >= self.HEAP_SIZE or self.cells[idx]["marked"]:
                return
            self.cells[idx]["marked"] = True
            mark(self.cells[idx]["car"])
            mark(self.cells[idx]["cdr"])
        
        mark(root_env)
        
        # 2. SWEEP
        purged = 0
        self.free_list = 0
        for i in range(1, self.HEAP_SIZE):
            if self.cells[i]["marked"]:
                self.cells[i]["marked"] = False
            else:
                self.cells[i]["car"] = 0
                self.cells[i]["cdr"] = self.free_list
                self.free_list = i
                purged += 1
        return purged

# テスト走行の即時実行
if __name__ == "__main__":
    vm = AnnotateVM()
    # 仮想ディレクトリをセクタ0に書き込みテスト
    mock_dir = [10, 20, 30]
    vm.prim_fdd_write(0, mock_dir)
    print("【VFDDテスト】セクタ0から想起された目次ポインタ:", vm.prim_fdd_read(0))
    
    # 負荷をかけてGCを作動させるテスト
    for i in range(1, 110):
        vm.cells[i]["car"] = 999  # 不要なゴミデータの蓄積
    purged_cells = vm.garbage_collect(root_env=0)
    print(f"【GCテスト】代謝システム作動。不要な過去の記憶を {purged_cells} セル忘却し、更地に戻しました。")