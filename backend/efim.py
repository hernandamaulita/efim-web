import pandas as pd
from collections import defaultdict

class Element:
    def __init__(self, tid, iutils, rutils):
        self.tid = tid        # Transaction ID
        self.iutils = iutils  # Item Utility
        self.rutils = rutils  # Remaining Utility 
class UtilityList:
    def __init__(self, item):
        self.item = item
        self.elements = []
        self.sum_iutils = 0
        self.sum_rutils = 0

    def add_element(self, element):
        self.elements.append(element)
        self.sum_iutils += element.iutils
        self.sum_rutils += element.rutils

class EFIM:
    def __init__(self, min_util, kolom_id_transaksi='ID_PENJUALAN', kolom_id_item='KODE_BARANG', kolom_utilitas='UTILITY'):
        self.min_util = min_util
        self.kolom_id_transaksi = kolom_id_transaksi
        self.kolom_id_item = kolom_id_item
        self.kolom_utilitas = kolom_utilitas
        self.high_utility_itemsets = []
        self.transaksi = []
        self.items_twu = defaultdict(int)
        self.eucs = defaultdict(int)  # Untuk Estimated Utility Co-occurrence Structure (EUCS)

    def muat_data(self, data_transaksi):
        transaksi_dict = defaultdict(list)
        for _, row in data_transaksi.iterrows():
            transaksi_dict[row[self.kolom_id_transaksi]].append((row[self.kolom_id_item], row[self.kolom_utilitas]))
        
        for id_transaksi, items in transaksi_dict.items():
            self.transaksi.append((id_transaksi, items))
        print("Data transaksi dimuat.")

    def hitung_TWU(self):
        #Menghitung Transaction Weighted Utilization (TWU) untuk semua item#
        for tid, items in self.transaksi:
            transaksi_utilitas = sum(util for _, util in items)
            for item, _ in items:
                self.items_twu[item] += transaksi_utilitas
        print(f"TWU per item: {dict(self.items_twu)}")

    def hitung_EUCS(self):
        # Membangun Estimated Utility Co-occurrence Structure (EUCS) #
        for tid, items in self.transaksi:
            item_set = set(item for item, _ in items)
            transaksi_utilitas = sum(util for _, util in items) #total utilitas dari semua item di transaksi tersebut 
            for item1 in item_set:
                for item2 in item_set:
                    if item1 != item2:
                        self.eucs[(item1, item2)] += transaksi_utilitas

    def buat_utility_list(self, items):
         # Membuat Utility List untuk setiap item yang lolos TWU, dengan Transaction Merging #
        utility_lists = dict()
        for item in items:
            utility_lists[item] = UtilityList(item)

        # Transaction Merging: group transaksi yang punya itemset sama
        merged_transaksi = defaultdict(list)
        for tid, transaksi_items in self.transaksi:
            itemset = frozenset(item for item, _ in transaksi_items if item in items)
            merged_transaksi[itemset].append((tid, transaksi_items))

        for itemset, transaksi_group in merged_transaksi.items():
            if not itemset:
                continue
            # Kalau ada lebih dari satu transaksi yang sama, merge mereka
            combined_items = []
            for _, items_list in transaksi_group:
                combined_items.extend(items_list)
            
            # Hitung ulang transaksi setelah merge
            transaksi_items = [item for item in combined_items if item[0] in items]
            transaksi_items.sort(key=lambda x: (self.items_twu[x[0]], x[0]))  # Sort by TWU naik

            remaining_utility = sum(util for _, util in transaksi_items)

            for i in range(len(transaksi_items)):
                item, utilitas = transaksi_items[i]
                remaining_utility -= utilitas
                e = Element("-".join(str(tid) for tid, _ in transaksi_group), utilitas, remaining_utility)
                utility_lists[item].add_element(e)

        return utility_lists

    def prune_items_by_twu(self):
        # Mengambil item dengan TWU >= min_util #
        return {item for item, twu in self.items_twu.items() if twu >= self.min_util}

    def efim_recursive(self, prefix, utility_lists, items):
        # Algoritma recursive EFIM dengan LU-Prune dan Upper Bound Check #
        for i in range(len(items)):
            Xi = items[i]
            ulist_Xi = utility_lists[Xi]

            # Simpan high upython app.pytility itemset
            if ulist_Xi.sum_iutils >= self.min_util:
                self.high_utility_itemsets.append((prefix + [Xi], ulist_Xi.sum_iutils))

            # LU-Prune: lanjut mining kalau sum_iutils + sum_rutils masih layak
            if ulist_Xi.sum_iutils + ulist_Xi.sum_rutils >= self.min_util:
                exULs = dict()
                for j in range(i + 1, len(items)):
                    Xj = items[j]

                    # Cek menggunakan EUCS sebelum konstruksi utility list
                    if (Xi, Xj) in self.eucs and self.eucs[(Xi, Xj)] < self.min_util:
                        continue

                    exUL = self.construct_utility_list(ulist_Xi, utility_lists[Xj])

                    # Upper Bound Check setelah construct
                    if exUL and exUL.sum_iutils + exUL.sum_rutils >= self.min_util:
                        exULs[Xj] = exUL

                if exULs:
                    self.efim_recursive(prefix + [Xi], exULs, list(exULs.keys()))

    def construct_utility_list(self, ulistP, ulistQ):
        # Mengkonstruksi utility list baru untuk gabungan item P dan Q #
        ulist = UtilityList(ulistQ.item)
        idxP = 0
        idxQ = 0
        while idxP < len(ulistP.elements) and idxQ < len(ulistQ.elements):
            eP = ulistP.elements[idxP]
            eQ = ulistQ.elements[idxQ]
            if eP.tid == eQ.tid:
                new_element = Element(
                    eP.tid,
                    eP.iutils + eQ.iutils,
                    eQ.rutils
                )
                ulist.add_element(new_element)
                idxP += 1
                idxQ += 1
            elif eP.tid < eQ.tid:
                idxP += 1
            else:
                idxQ += 1

        if not ulist.elements:
            return None
        return ulist

    def jalankan(self, data_transaksi):
        # Menjalankan semua proses EFIM#
        self.muat_data(data_transaksi)
        self.hitung_TWU()
        self.hitung_EUCS()  # Tambahkan hitung EUCS
        item_terpilih = self.prune_items_by_twu()
        print(f"Item terpilih setelah TWU pruning: {item_terpilih}")

        if not item_terpilih:
            print("Tidak ada item yang memenuhi batas minimum utilitas.")
            return
        
        utility_lists = self.buat_utility_list(item_terpilih)
        items_sorted = sorted(item_terpilih, key=lambda x: (self.items_twu[x], x))  # Sort berdasarkan TWU
        self.efim_recursive([], utility_lists, items_sorted)

def jalankan_algoritma_efim(data_transaksi, batas_utilitas_minimum, kolom_id_transaksi='ID_PENJUALAN', kolom_id_item='KODE_BARANG', kolom_utilitas='UTILITY'):
    efim = EFIM(
        batas_utilitas_minimum,
        kolom_id_transaksi=kolom_id_transaksi,
        kolom_id_item=kolom_id_item,
        kolom_utilitas=kolom_utilitas
    )
    efim.jalankan(data_transaksi)
    return efim.high_utility_itemsets
