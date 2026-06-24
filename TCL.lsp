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

;;; --- grread tabanli secim: gecerli nesne ya da 'ENTER doner ----------------
;;; Bos alana / yanlis nesneye tiklayinca IPTAL ETMEZ, tekrar sorar.
;;; Sadece ENTER (veya Space) basilinca 'ENTER doner -> komut biter.
(defun tcl:pick (msg types errmsg / data code pt ss ent etype res)
  (setq res nil)
  (princ msg)
  (while (null res)
    (setq data (grread nil 4 2)
          code (car data))
    (cond
      ;; --- klavye ---
      ((= code 2)
       (cond
         ((member (cadr data) '(13 32)) (setq res 'ENTER))  ; Enter / Space -> bitir
         (T (princ "\n  (Bitirmek icin ENTER, secmek icin nesneye tiklayin)")
            (princ msg))))
      ;; --- sol tik (nokta) ---
      ((= code 3)
       (setq pt (cadr data)
             ss (ssget pt))
       (if ss
         (progn
           (setq ent   (ssname ss 0)
                 etype (cdr (assoc 0 (entget ent))))
           (if (member etype types)
             (setq res ent)
             (progn (princ errmsg) (princ msg))))
         (progn
           (princ "\n  >> Bos alana tiklandi, tekrar deneyin.")
           (princ msg))))
      ;; --- diger girdileri yoksay (komut iptal olmaz) ---
      (T nil)
    )
  )
  res
)

;;; ===========================================================================
(defun c:TCL ( / *error* tEnt cEnt rows txt cen pt usez ans looping
                 doc acsp tbl nrows ncols rowh colw th i r c )

  (defun *error* (msg)
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\nHata: " msg)))
    (princ)
  )

  (vl-load-com)
  (setq rows '())
  (princ "\n=== TEXT + CIRCLE Koordinat Listesi ===")

  ;; ------------------------ Z kolonu secimi ---------------------------------
  (initget "Evet Hayir")
  (setq ans  (getkword "\nZ koordinati dahil edilsin mi? [Evet/Hayir] <Evet>: ")
        usez (not (= ans "Hayir")))   ; varsayilan: Z dahil

  ;; ------------------------ Secim dongusu -----------------------------------
  ;; Bos/yanlis tiklama IPTAL ETMEZ; sadece ENTER komutu bitirir.
  (setq looping T)
  (while looping
    ;; 1) Baslik (TEXT/MTEXT) sec
    (setq tEnt (tcl:pick "\nBaslik icin TEXT/MTEXT secin (bitirmek icin ENTER): "
                         '("TEXT" "MTEXT")
                         "\n  >> Bu nesne TEXT/MTEXT degil, tekrar deneyin."))
    (if (eq tEnt 'ENTER)
      (setq looping nil)                       ; ENTER -> komutu bitir
      (progn
        (setq txt (tcl:gettext tEnt))
        ;; 2) Circle sec
        (setq cEnt (tcl:pick "\nKoordinati alinacak CIRCLE secin (bitirmek icin ENTER): "
                             '("CIRCLE")
                             "\n  >> Bu nesne CIRCLE degil, tekrar deneyin."))
        (if (eq cEnt 'ENTER)
          (progn                               ; ENTER -> son baslik iptal, komutu bitir
            (princ "\n  Circle secilmedi; son baslik iptal edildi.")
            (setq looping nil))
          (progn
            (setq cen  (cdr (assoc 10 (entget cEnt)))
                  rows (cons (list txt cen) rows))
            (princ (strcat "\n  + Eklendi: \"" txt "\"  ("
                           (rtos (car cen) 2 3) ", "
                           (rtos (cadr cen) 2 3) ", "
                           (rtos (caddr cen) 2 3) ")"))
          )
        )
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

          (setq ncols (if usez 4 3)
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
          (if usez (vla-SetText tbl 1 3 "Z"))

          ;; Veri satirlari
          (setq i 0)
          (foreach row rows
            (setq cen (cadr row))
            (vla-SetText tbl (+ i 2) 0 (car row))
            (vla-SetText tbl (+ i 2) 1 (rtos (car  cen) 2 3))
            (vla-SetText tbl (+ i 2) 2 (rtos (cadr cen) 2 3))
            (if usez (vla-SetText tbl (+ i 2) 3 (rtos (caddr cen) 2 3)))
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
