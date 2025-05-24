from pysat.solvers import Glucose4
from pysat.formula import CNF, IDPool
import time

# -----------------------------------------------------------
# 1) Hỗ trợ đọc/ghi file (hoặc tùy biến theo định dạng yêu cầu)
# -----------------------------------------------------------
def add_clause_unique(cnf_obj, clause):
    """
    Thêm mệnh đề vào CNF nếu chưa có mệnh đề nào giống nó.
    """
    clause.sort()  # Sắp xếp tăng dần
    if clause not in cnf_obj.clauses:
        cnf_obj.append(clause)

def read_input(filename):
    """
    Giả sử file input dạng:
    3, _, 2, _
    _, _, 2, _
    _, 3, 1, _

    Trả về grid là danh sách 2D,
    mỗi phần tử có thể là:
      - int (nếu là số)
      - "_" (nếu chưa biết)
      - "T" hoặc "G" (nếu biết chắc bẫy hoặc đá quý)
    """
    grid = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # tách bằng dấu phẩy
            parts = [x.strip() for x in line.split(',')]
            row_data = []
            for p in parts:
                if p.isdigit():
                    row_data.append(int(p))  # ô số
                else:
                    row_data.append(p)  # "_", "T", "G" hoặc kí hiệu khác
            grid.append(row_data)
    return grid


def write_output(filename, grid):
    """
    Ghi kết quả ra file, ví dụ:
    3, T, 2, G
    T, T, 2, G
    T, 3, 1, G
    """
    with open(filename, 'w', encoding='utf-8') as f:
        for row in grid:
            row_str = ", ".join(str(item) for item in row)
            f.write(row_str + "\n")


# -----------------------------------------------------------
# 2) Hàm lấy danh sách ô lân cận (8 hướng hoặc 4 hướng tuỳ luật)
# -----------------------------------------------------------
def get_neighbors(r, c, R, C):
    """
    Lấy các ô xung quanh (8 hướng).
    Nếu chỉ được 4 hướng, bạn điều chỉnh lại.
    """
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < R and 0 <= nc < C:
                neighbors.append((nr, nc))
    return neighbors


# -----------------------------------------------------------
# 3) Hàm mã hoá ràng buộc "chính xác k biến True"
#    (exactly-k-of list_of_vars) thành CNF
# -----------------------------------------------------------
def exactly_k(variables, k, pool):
    """
    Trả về list các mệnh đề CNF (dạng list các list)
    để ràng buộc "chính xác k trong dãy biến = True".

    Cách đơn giản (sẽ tạo nhiều mệnh đề) là:
      - sum <= k
      - sum >= k
    sum <= k có thể mã hoá bằng:
      với mọi tổ hợp (k+1) biến, không thể tất cả cùng True.
    sum >= k có thể mã hoá bằng:
      với mọi tổ hợp (len(vars) - k + 1) biến, không thể tất cả cùng False.
    """
    clauses = []
    n = len(variables)

    # Nếu k > n, vô lý -> không có nghiệm
    if k > n:
        # ép xung đột
        clauses.append([-pool.id(f"CONFLICT")])
        return clauses

    # 3a) sum <= k
    # "Không được có (k+1) biến cùng True"
    from itertools import combinations
    if k < n:
        for combo in combinations(variables, k + 1):
            # combo là 1 tổ hợp k+1 biến
            # Mệnh đề: không thể tất cả True
            # Tức là (¬x1) v (¬x2) v ... v (¬x_{k+1})
            clause = []
            for v in combo:
                clause.append(-v)  # -v = NOT v
            clauses.append(clause)

    # 3b) sum >= k
    # "Không được có (n-k+1) biến cùng False"
    if k > 0:
        for combo in combinations(variables, n - k + 1):
            # combo là 1 tổ hợp (n-k+1) biến
            # Mệnh đề: không thể tất cả False
            # Tức là (x1) v (x2) v ... v (x_{...})
            clause = []
            for v in combo:
                clause.append(v)  # v = NOT(False)
            clauses.append(clause)

    return clauses


# -----------------------------------------------------------
# 4) HÀM CHÍNH: Tạo CNF từ lưới
# -----------------------------------------------------------
def encode_to_cnf(grid):
    R = len(grid)
    C = len(grid[0])
    var_id_pool = IDPool()  # Cấp phát ID cho biến
    varmap = {}  # map (r,c) -> int (ID)
    cnf_obj = CNF()

    # Bước 1: Gán biến cho các ô "_" (chưa biết).
    for r in range(R):
        for c in range(C):
            cell = grid[r][c]
            if cell == '_':
                # Tạo ID cho ô (r,c)
                varmap[(r, c)] = var_id_pool.id(f"trap_{r}_{c}")
            elif cell == 'T':
                vid = var_id_pool.id(f"trap_{r}_{c}")
                varmap[(r, c)] = vid
                # Mệnh đề 1-literal: (vid), ép biến này phải True
                add_clause_unique(cnf_obj, [vid])
            elif cell == 'G':
                vid = var_id_pool.id(f"trap_{r}_{c}")
                varmap[(r, c)] = vid
                # Mệnh đề 1-literal: (-vid) => biến này phải False
                add_clause_unique(cnf_obj, [-vid])

    # Bước 2: Tạo ràng buộc cho các ô số
    for r in range(R):
        for c in range(C):
            cell = grid[r][c]
            if isinstance(cell, int):
                neighs = get_neighbors(r, c, R, C)
                neighbor_vars = []
                for (nr, nc) in neighs:
                    if (nr, nc) in varmap:
                        neighbor_vars.append(varmap[(nr, nc)])

                k = cell  # Số bẫy lân cận phải bằng cell
                clause_list = exactly_k(neighbor_vars, k, var_id_pool)
                for cl in clause_list:
                    add_clause_unique(cnf_obj, cl)

    return cnf_obj, varmap



# -----------------------------------------------------------
# 5) Giải CNF và suy ra kết quả
# -----------------------------------------------------------
def solve_puzzle(cnf_obj, varmap, grid):
    solver = Glucose4()
    # Nạp tất cả mệnh đề vào solver
    for clause in cnf_obj.clauses:
        solver.add_clause(clause)

    sat = solver.solve()
    if not sat:
        print("Không có nghiệm!")
        return None

    model = solver.get_model()
    # model là danh sách các số nguyên, dương => biến True, âm => biến False
    # Ta tạo set để kiểm tra nhanh
    true_vars = set(lit for lit in model if lit > 0)

    R = len(grid)
    C = len(grid[0])
    result_grid = []
    for r in range(R):
        row_res = []
        for c in range(C):
            cell = grid[r][c]
            if isinstance(cell, int):
                # Giữ nguyên số
                row_res.append(cell)
            elif cell == 'T':
                # Đã cố định là bẫy
                row_res.append('T')
            elif cell == 'G':
                # Đã cố định là gem
                row_res.append('G')
            elif cell == '_':
                # Cần xem biến (r,c) có True/False
                var_id = varmap[(r, c)]
                if var_id in true_vars:
                    row_res.append('T')
                else:
                    row_res.append('G')
            else:
                # Ký hiệu gì khác tuỳ ý
                row_res.append(cell)
        result_grid.append(row_res)

    return result_grid


# -----------------------------------------------------------
# DEMO: Thực thi cho ví dụ (đọc file / ghi file)
# -----------------------------------------------------------
def main():
    input_file = "input_3.txt"
    output_file = "output_3.txt"

    # 1) Đọc input
    grid = read_input(input_file)

    # 2) Tạo CNF
    start_time = time.time()
    cnf_obj, varmap = encode_to_cnf(grid)

    # 3) Giải SAT
    result = solve_puzzle(cnf_obj, varmap, grid)
    end_time = time.time()
    if result:
        # In ra màn hình
        print("Kết quả:")
        for row in result:
            print(row)
        print(f"Thời gian chạy: {end_time - start_time:.10f} giây")
        # 4) Ghi output
        write_output(output_file, result)

# Nếu muốn chạy trực tiếp, bỏ comment:
main()
