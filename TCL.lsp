;;; ===========================================================================
;;; TCL.LSP  -  Text Basligi + Circle Koordinat Listesi
;;; ---------------------------------------------------------------------------
;;; Komut : TCL
;;;
;;; Calisma sekli:
;;;   1. Bir TEXT / MTEXT secersiniz  -> bu satirin BASLIGI olur.
;;;   2. Bir CIRCLE secersiniz        -> dairenin merkez koordinatlari
;;;                                       o satira yazilir.
;;;   3. Bu islem siz bitirene kadar tekrarlanir (her cift alt alta eklenir).
;;;   4. ENTER'a basinca secim biter.
;;;   5. Tiklayacaginiz noktaya tum kayitlar bir TABLO olarak yazdirilir.
;;;
;;; Tablo kolonlari: BASLIK | X | Y | Z
;;; ===========================================================================

;;; --- MTEXT formatlama kodlarini temizleyen yardimci fonksiyon --------------
(defun tcl:cleanmtext (s / r)
  (setq r s)
  ;; satir sonlarini bosluk yap
  (while (vl-string-search "\\P" r)
    (setq r (vl-string-subst " " "\\P" r)))
  ;; suslu parantezleri kaldir
  (while (vl-string-search "{" r) (setq r (vl-string-subst "" "{" r)))
  (while (vl-string-search "}" r) (setq r (vl-string-subst "" "}" r)))
  r
)

;;; --- Secilen text nesnesinin metnini al ------------------------------------
(defun tcl:gettext (ename / d typ s)
  (setq d   (entget ename)
        typ (cdr (assoc 0 d)))
  (cond
    ((= typ "TEXT")  (cdr (assoc 1 d)))
    ((= typ "MTEXT")
     (setq s (vla-get-TextString (vlax-ename->vla-object ename)))
     (tcl:cleanmtext s))
    (T nil)
  )
)

;;; ===========================================================================
(defun c:TCL ( / *error* tEnt cEnt cData rows txt cen pt
                 doc acsp tbl nrows ncols rowh colw th i r c )

  (defun *error* (msg)
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\nHata: " msg)))
    (princ)
  )

  (vl-load-com)
  (setq rows '())
  (princ "\n=== TEXT + CIRCLE Koordinat Listesi ===")

  ;; ------------------------ Secim dongusu -----------------------------------
  (while
    (progn
      (setq tEnt (car (entsel "\nBaslik icin TEXT/MTEXT secin (bitirmek icin ENTER): ")))
      (if tEnt
        (progn
          (setq txt (tcl:gettext tEnt))
          (cond
            ((null txt)
             (princ "\n  >> Secilen nesne TEXT/MTEXT degil. Tekrar deneyin.")
             T)
            (T
             ;; --- Circle secimi ---
             (setq cEnt (car (entsel "\nKoordinati alinacak CIRCLE secin: ")))
             (cond
               ((null cEnt)
                (princ "\n  >> Circle secilmedi, bu kayit atlandi.")
                T)
               (T
                (setq cData (entget cEnt))
                (if (= (cdr (assoc 0 cData)) "CIRCLE")
                  (progn
                    (setq cen  (cdr (assoc 10 cData))
                          rows (cons (list txt cen) rows))
                    (princ (strcat "\n  + Eklendi: \"" txt "\"  ("
                                   (rtos (car cen) 2 3) ", "
                                   (rtos (cadr cen) 2 3) ", "
                                   (rtos (caddr cen) 2 3) ")"))
                    T)
                  (progn
                    (princ "\n  >> Secilen nesne CIRCLE degil, bu kayit atlandi.")
                    T)
                )
               )
             )
            )
          )
        )
        nil ; ENTER -> donguyu bitir
      )
    )
  )

  (setq rows (reverse rows))

  ;; ------------------------ Tablo olusturma ---------------------------------
  (if (null rows)
    (princ "\nHic kayit eklenmedi. Islem iptal.")
    (progn
      (setq pt (getpoint "\nTablonun yerlesecegi noktayi secin: "))
      (if (null pt)
        (princ "\nNokta secilmedi. Islem iptal.")
        (progn
          (setq th (getvar "TEXTSIZE"))
          (if (or (null th) (<= th 0.0)) (setq th 2.5))

          (setq ncols 4
                nrows (+ (length rows) 2)   ; baslik satiri + kolon basliklari + veriler
                rowh  (* th 2.0)
                colw  (* th 14.0)
                doc   (vla-get-ActiveDocument (vlax-get-acad-object))
                acsp  (vlax-get-property doc
                        (if (= (getvar "CTAB") "Model") 'ModelSpace 'PaperSpace)))

          (setq tbl (vla-AddTable acsp (vlax-3d-point pt) nrows ncols rowh colw))

          ;; Baslik satiri (otomatik olarak kolonlar boyunca birlestirilir)
          (vla-SetText tbl 0 0 "CIRCLE KOORDINAT LISTESI")

          ;; Kolon basliklari
          (vla-SetText tbl 1 0 "BASLIK")
          (vla-SetText tbl 1 1 "X")
          (vla-SetText tbl 1 2 "Y")
          (vla-SetText tbl 1 3 "Z")

          ;; Veri satirlari
          (setq i 0)
          (foreach row rows
            (setq cen (cadr row))
            (vla-SetText tbl (+ i 2) 0 (car row))
            (vla-SetText tbl (+ i 2) 1 (rtos (car  cen) 2 3))
            (vla-SetText tbl (+ i 2) 2 (rtos (cadr cen) 2 3))
            (vla-SetText tbl (+ i 2) 3 (rtos (caddr cen) 2 3))
            (setq i (1+ i))
          )

          ;; Tum hucrelerin metin yuksekligini ayarla
          (setq r 0)
          (while (< r nrows)
            (setq c 0)
            (while (< c ncols)
              (vl-catch-all-apply 'vla-SetCellTextHeight (list tbl r c th))
              (setq c (1+ c))
            )
            (setq r (1+ r))
          )

          (vla-Update tbl)
          (princ (strcat "\nTablo olusturuldu. Toplam " (itoa (length rows)) " kayit yazildi."))
        )
      )
    )
  )
  (princ)
)

(princ "\nTCL.LSP yuklendi. Calistirmak icin komut satirina  TCL  yazin.")
(princ)
