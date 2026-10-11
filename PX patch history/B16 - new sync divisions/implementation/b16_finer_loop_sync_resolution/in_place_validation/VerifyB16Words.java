// SPDX-License-Identifier: GPL-2.0-or-later
import java.nio.file.*;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.assembler.Assembler;
import ghidra.app.plugin.assembler.Assemblers;
import ghidra.app.plugin.assembler.sleigh.sem.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.Instruction;

public class VerifyB16Words extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();
  Assembler assembler=Assemblers.getAssembler(currentProgram);
  List<String> lines=Files.readAllLines(Path.of(args[0]));
  List<String> output=new ArrayList<>();
  output.add("Independent verification: Ghidra "+getGhidraVersion()+" language "+currentProgram.getLanguageID());
  for(String line:lines){
   String[] f=line.split("\t",3);Address a=toAddr(f[0]);long word=Long.parseUnsignedLong(f[1],16);
   byte[] expected=new byte[]{(byte)word,(byte)(word>>8),(byte)(word>>16),(byte)(word>>24)};
   String syntax=f[2].replaceAll("^addu ([^,]+),([^,]+),zero$","move $1,$2").replaceAll("^addiu ([^,]+),zero,","li $1,");
   byte[] actual=assembler.assembleLine(a,syntax);
   if(!Arrays.equals(actual,expected)) {
    boolean match=false;
    for(AssemblyResolution resolution:assembler.resolveLine(a,syntax)) {
     if(resolution instanceof AssemblyResolvedPatterns pattern && pattern.getContext().combine(assembler.getContextAt(a))!=null) {
      int count=0;
      for(byte[] option:pattern.possibleInsVals(assembler.getContextAt(a))) {
       if(Arrays.equals(option,expected)){match=true;break;}
       if(++count>1024)break;
      }
     }
    }
    if(!match)throw new Exception("ASSEMBLY MISMATCH "+line+" actual="+HexFormat.of().formatHex(actual));
    output.add("Assembler alias alternative verified: "+f[0]+" "+syntax);
   }
   currentProgram.getMemory().setBytes(a,expected);
  }
  long[][] spans={{0x9d04fa74L,0x9d04fb0fL},{0x9d060278L,0x9d060297L},{0x9d06209cL,0x9d0620abL}};
  for(long[] span:spans){
   Address lo=toAddr(span[0]),hi=toAddr(span[1]);
   new DisassembleCommand(lo,new AddressSet(lo,hi),false).applyTo(currentProgram,monitor);
  }
  for(String line:lines){
   String[] f=line.split("\t",3);Address a=toAddr(f[0]);Instruction ins=getInstructionAt(a);
   if(ins==null) {new DisassembleCommand(a,new AddressSet(a,a.add(3)),false).applyTo(currentProgram,monitor);ins=getInstructionAt(a);}
   if(ins==null||ins.getLength()!=4)throw new Exception("DISASSEMBLY FAILED "+line);
   output.add(f[0]+"\t"+f[1]+"\t"+ins+"\tdelayDepth="+ins.getDelaySlotDepth()+"\tinDelaySlot="+ins.isInDelaySlot()+"\tflows="+Arrays.toString(ins.getFlows()));
  }
  output.add("PASS: "+lines.size()+" exact assembly matches and independent instruction decodes; changes confined to scratch Ghidra project.");
  Files.write(Path.of(args[1]),output);println(output.get(output.size()-1));
 }
}
