# SPDX-License-Identifier: GPL-2.0-or-later
"""B9 .2.3 source snapshot for review; paired with b9_2_3_mips.py.

Emit directly into final factory-based ownership; no intermediate firmware,
private payload inputs, new timer, frame, RAM allocation or compiler object.
"""
from b9_2_3_mips import emit

BASE=0x9d000000
PANEL=(0x9d02a3d0,0x9d02a808,0x9d02aabc,0x9d02bcc8,0x9d02dcf0,0x9d02e0c0)

def labelled(rows,start):
    labels={};body=[]
    for row in rows:
        if row[0].endswith(':'):
            name=row[0][:-1]
            if name in labels:raise ValueError('Duplicate B9 label')
            labels[name]=start+4*len(body)
        else:body.append(row)
    return emit(body,start,labels),labels

def writes():
    result=[]
    def block(pc,rows,owner,labels=None):
        result.append((pc,emit(rows,pc,labels),owner))
    helper=BASE+0xd84
    rows=[('addu','s0','s3','s0'),('lw','t1',0x44,'sp'),('lui','t0',0x9d02)]
    for ret in PANEL:
        rows.extend([('ori','t2','t0',ret&65535),('beq','t1','t2',helper+18*4)])
    rows.extend([
        ('nop',),('j',BASE+0x23558),('addiu','v0','zero',500),
        ('addiu','t2','zero',125),
        ('beq','t3','zero',helper+23*4),('sh','t2',18,'s0'),
        ('j',BASE+0x23558),('addiu','v0','zero',125),
        ('j',BASE+0x2355c),('nop',),
        ('addu','t0','s3','t0'),('lh','v0',18,'t0'),('movz','v0','s1','v0'),
        ('sw','v0',0,'t0'),('j',BASE+0x53330),('addiu','s5','s5',1),
    ])
    if len(rows)!=31:raise ValueError('B9 reserved helper extent changed')
    block(helper,rows,'B9 panel countdown and expiry helper')
    for pc,flag in ((BASE+0x23550,0),(BASE+0x235e4,1)):
        block(pc,[('j',helper),('addiu','t3','zero',flag)],'B9 panel wrapper hook')
    block(BASE+0x53790,[('j',helper+25*4),('lw','t0',0x6c,'sp')],'B9 changed-selection expiry hook')
    start,end=BASE+0x36690,BASE+0x367b4
    rows=[
        # Original white text/font setup, retained before choosing either source.
        ('lui','a0',0x9d06),('addiu','a0','a0',-23484),
        ('addiu','v0','zero',15),('sh','v0',-32232,'gp'),
        ('lui','v0',0x0f0f),('addiu','v0','v0',0x0f0f),
        ('jal',BASE+0x689d8),('sw','v0',-32240,'gp'),
        # All six real panel sources queue mode=2 in slot A. A countdown of zero
        # is still pending until serviced. Idle or any other source uses layers.
        ('lw','t0',-0x7c84,'gp'),('bltz','t0','applied'),('lui','v1',0x8005),
        ('lh','t1',-0x7c72,'gp'),('addiu','t2','zero',125),('bne','t1','t2','applied'),
        ('lhu','t0',0x2e5e,'v1'),('lhu','t2',-0x7ca4,'gp'),
        ('bne','t0','t2','applied'),('lhu','t1',0x2e60,'v1'),
        ('lhu','t2',-0x7c7c,'gp'),('beq','t1','t2','chosen'),('nop',),
        ('applied:',),('lhu','t0',0x2e5c,'v1'),('xori','t0','t0',1),('sltiu','t0','t0',1),
        ('sll','t0','t0',1),('addu','v1','v1','t0'),
        ('lhu','t0',0x2e74,'v1'),('lhu','t1',0x2e78,'v1'),('srl','t1','t1',1),
        ('chosen:',),('sw','t1',0x48,'sp'),
        # Same U/F/A and one-based numbering conventions as the original title.
        ('sltiu','t2','t0',4),('bne','t2','zero','user'),('addiu','v0','zero',0x2055),
        ('sltiu','t2','t0',8),('bne','t2','zero','factory'),('addiu','v0','zero',0x2046),
        ('addiu','v0','zero',0x2041),('beq','zero','zero','bank'),('addiu','a0','t0',-7),
        ('factory:',),('beq','zero','zero','bank'),('addiu','a0','t0',-3),
        ('user:',),('addiu','a0','t0',1),
        ('bank:',),('sh','v0',16,'sp'),('sb','zero',18,'sp'),
        ('jal',BASE+0x5f770),('addiu','s1','sp',16),
        ('addu','a0','s1','zero'),('jal',BASE+0x8169c),('addu','a1','v0','zero'),
        ('addiu','a0','zero',8),('addu','a1','zero','zero'),
        ('jal',BASE+0x68d64),('addu','a2','s1','zero'),
        ('addiu','v0','zero',0x2050),('sh','v0',16,'sp'),('sb','zero',18,'sp'),
        ('lw','a0',0x48,'sp'),('jal',BASE+0x5f770),('addiu','a0','a0',1),
        ('addu','a0','s1','zero'),('jal',BASE+0x8169c),('addu','a1','v0','zero'),
        ('addiu','a0','zero',74),('addu','a1','zero','zero'),
        ('jal',BASE+0x68d64),('addu','a2','s1','zero'),
        ('j',BASE+0x36558),('lhu','a0',4,'s0'),
        # Relocate the original full-redraw bypass, which sits in the old title.
        ('full:',),('addiu','v0','zero',1),('sb','v0',-32750,'gp'),
        ('j',BASE+0x36558),('lhu','a0',4,'s0'),
    ]
    data,labels=labelled(rows,start)
    if len(data)>end-start:raise ValueError('B9 title exceeds original function allocation')
    data+=bytes(end-start-len(data))
    result.append((start,data,'B9 conditional requested-number title'))
    block(BASE+0x364b4,[('bne','v0','zero',labels['full'])],'B9 relocated full-redraw branch')
    return result
